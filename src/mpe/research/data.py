"""Historical data for experiments: replay access, forecast origins, inputs and realised targets.

Every read of observations goes through one of the two sanctioned accessors,
:func:`mpe.storage.repositories.get_history` (strict) or
:func:`mpe.storage.replay.get_reconstructed_history` (reconstructed), chosen by the experiment's
``knowledge_mode`` and never substituted. Rules (see docs/M2_RESEARCH_METHODOLOGY.md):

* An origin is a grid point ``t_o`` (an exchange session close, or an hourly sample bucket). Its
  information cutoff is ``t_o + cutoff_delay``; the context is read at that cutoff and nothing
  later can be in it.
* Missing observations stay missing (NaN in the context). Nothing is forward-filled here; a
  realised target that does not exist is never scored.
* An origin is excluded, with a recorded reason, if its own observation is not available at the
  cutoff, if the context has too few valid points or too large a missing fraction, or if the
  history contains duplicate timestamps.
* Realised targets are read once per asset at ``targets_as_of`` through the same accessor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mpe.clock import to_iso
from mpe.features.transforms import log_returns, logit, price_series, stock_log_returns
from mpe.research.config import Exclusion, ExperimentConfig
from mpe.storage.orm import Asset, Market, Resolution
from mpe.storage.replay import KnowledgeMode, get_reconstructed_history
from mpe.storage.repositories import asset_by_symbol, get_history

HOUR = pd.Timedelta(hours=1)


# ------------------------------------------------------------------ replay dispatch
class ReplayModeMismatch(RuntimeError):
    pass


def read_history(
    session: Session,
    mode: KnowledgeMode,
    asset_id: int,
    as_of: datetime,
    interval: str,
    source: str,
    start: datetime | None = None,
    extra_latency: timedelta = timedelta(0),
) -> pd.DataFrame:
    """History through the accessor for ``mode``; the only way this package reads observations."""
    mode = KnowledgeMode(mode)
    if mode == KnowledgeMode.STRICT:
        if extra_latency:
            raise ValueError("strict replay has no extra latency setting")
        df = get_history(session, asset_id, as_of, interval, source=source, start=start)
    else:
        df = get_reconstructed_history(
            session, asset_id, as_of, interval, source=source, start=start, extra_latency=extra_latency
        )
    if df.attrs.get("knowledge_mode") != mode.value:
        raise ReplayModeMismatch(
            f"asked for {mode.value}, accessor returned {df.attrs.get('knowledge_mode')}"
        )
    return df


# ------------------------------------------------------------------ grids
class Grid:
    """Sorted UTC grid of expected observation timestamps (session closes or hours)."""

    def __init__(self, points: pd.DatetimeIndex):
        if points.tz is None:
            raise ValueError("grid must be timezone-aware")
        self.points = pd.DatetimeIndex(points).tz_convert("UTC")
        if not self.points.is_monotonic_increasing or self.points.has_duplicates:
            raise ValueError("grid must be strictly increasing")

    def pos(self, t: pd.Timestamp) -> int:
        i = int(self.points.searchsorted(t))
        if i >= len(self.points) or self.points[i] != t:
            raise KeyError(f"{t} is not a grid point")
        return i

    def upto(self, t: pd.Timestamp, n: int) -> pd.DatetimeIndex:
        """The last ``n`` grid points at or before ``t`` (fewer if the grid starts later)."""
        j = int(self.points.searchsorted(t, side="right"))
        return self.points[max(0, j - n) : j]

    def after(self, t: pd.Timestamp, n: int) -> pd.DatetimeIndex:
        j = int(self.points.searchsorted(t, side="right"))
        out = self.points[j : j + n]
        if len(out) < n:
            raise ValueError(f"grid ends before {n} points after {t}")
        return out

    def between(self, a: pd.Timestamp, b: pd.Timestamp) -> pd.DatetimeIndex:
        return self.points[(self.points >= a) & (self.points <= b)]


def stock_grid(calendar: str, start: datetime, end: datetime) -> Grid:
    """Session closes (UTC) of an exchange calendar, early closes included."""
    import exchange_calendars as xc

    cal = xc.get_calendar(calendar, start="2000-01-01", end=(end + timedelta(days=400)).strftime("%Y-%m-%d"))
    closes = cal.closes
    closes = closes[(closes.index >= pd.Timestamp(start.date())) & (closes.index <= pd.Timestamp(end.date()))]
    return Grid(pd.DatetimeIndex(closes.to_numpy()).tz_localize("UTC") if closes.dt.tz is None
                else pd.DatetimeIndex(closes).tz_convert("UTC"))  # fmt: skip


def hourly_grid(start: datetime, end: datetime) -> Grid:
    a = pd.Timestamp(start).tz_convert("UTC").floor("h")
    b = pd.Timestamp(end).tz_convert("UTC").ceil("h")
    return Grid(pd.date_range(a, b, freq="h"))


# ------------------------------------------------------------------ assets
@dataclass(frozen=True)
class ResearchAsset:
    key: str  # stock symbol or Polymarket condition id
    asset_id: int
    label: str
    closing_time: datetime | None = None
    meta: dict = field(default_factory=dict)


def resolve_assets(session: Session, cfg: ExperimentConfig) -> tuple[list[ResearchAsset], list[Exclusion]]:
    out: list[ResearchAsset] = []
    excluded: list[Exclusion] = []
    for key in cfg.assets:
        if cfg.domain == "stocks":
            a = asset_by_symbol(session, cfg.source, key)
            if a is None:
                excluded.append(Exclusion(asset=key, reason="not in database"))
                continue
            if a.asset_type not in ("stock", "etf", "index"):
                excluded.append(
                    Exclusion(asset=key, reason=f"asset_type {a.asset_type} is not on {cfg.calendar}")
                )
                continue
            out.append(ResearchAsset(key, a.id, key, meta={"asset_type": a.asset_type}))
        else:
            m = session.scalar(
                select(Market).where(Market.provider == "polymarket", Market.provider_market_id == key)
            )
            if m is None:
                excluded.append(Exclusion(asset=key, reason="market not in database"))
                continue
            tok = session.scalar(select(Asset).where(Asset.market_id == m.id, Asset.outcome_side == "YES"))
            if tok is None:
                excluded.append(Exclusion(asset=key, reason="no YES token asset"))
                continue
            if m.yes_token_id and tok.symbol != m.yes_token_id:
                excluded.append(
                    Exclusion(asset=key, reason="YES token asset does not match market.yes_token_id")
                )
                continue
            res = session.scalar(select(Resolution).where(Resolution.market_id == m.id))
            meta = {
                "question": m.question, "status": m.resolution_status, "category": m.category,
                "selection_reason": m.selection_reason, "yes_token": tok.symbol,
                "closing_time": to_iso(m.closing_time) if m.closing_time else None,
                "resolution": None if res is None else {
                    "outcome": res.outcome, "resolved_at": to_iso(res.resolved_at), "source": res.source},
            }  # fmt: skip
            out.append(ResearchAsset(key, tok.id, m.question, m.closing_time, meta))
    return out, excluded


def default_stock_universe(session: Session, source: str = "yfinance") -> list[str]:
    rows = session.scalars(
        select(Asset).where(Asset.provider == source, Asset.asset_type.in_(("stock", "etf", "index")))
        .order_by(Asset.id)
    ).all()  # fmt: skip
    return [a.symbol for a in rows]


def default_polymarket_universe(session: Session) -> list[str]:
    """Every selected market (open and resolved), in id order; not only markets still active."""
    rows = session.scalars(select(Market).where(Market.selected == 1).order_by(Market.id)).all()
    return [m.provider_market_id for m in rows]


# ------------------------------------------------------------------ series on a grid
@dataclass
class GridSeries:
    levels: np.ndarray  # price / probability on the grid, NaN = missing
    diagnostics: dict
    frame: pd.DataFrame  # the rows used, indexed by timestamp (provenance)


def levels_on_grid(df: pd.DataFrame, points: pd.DatetimeIndex, field: str) -> GridSeries:
    """Align a history frame to grid points without filling anything."""
    diag = {"rows": len(df), "duplicate_timestamps": 0, "off_grid_rows": 0,
            "missing_price_field": 0, "invalid_price": 0}  # fmt: skip
    if df.empty:
        return GridSeries(np.full(len(points), np.nan), diag, df)
    dup = int(df["timestamp"].duplicated().sum())
    diag["duplicate_timestamps"] = dup
    if len(points):
        inside = (df["timestamp"] >= points[0]) & (df["timestamp"] <= points[-1])
        on = df["timestamp"].isin(points)
        diag["off_grid_rows"] = int((inside & ~on).sum())
        df = df[on]
    null = df[field].isna()
    diag["missing_price_field"] = int(null.sum())
    df = df[~null].drop_duplicates("timestamp", keep=False)
    s = price_series(df, field) if len(df) else pd.Series(dtype="float64")
    bad = ~np.isfinite(s.to_numpy()) | (s.to_numpy() <= 0)
    diag["invalid_price"] = int(bad.sum())
    s = s[~bad]
    lv = s.reindex(points).to_numpy(dtype=np.float64)
    return GridSeries(lv, diag, df.set_index("timestamp", drop=False))


def target_values(cfg: ExperimentConfig, frame: pd.DataFrame, levels: np.ndarray,
                  points: pd.DatetimeIndex) -> np.ndarray:  # fmt: skip
    """Target-space values on ``points``. Returns: value at t is ln(P_t / P_prev grid point), NaN if
    either is missing (a return is never computed across a gap). Logits: logit of the YES price."""
    if cfg.target == "logit_price":
        return logit(levels, eps=cfg.logit_eps)
    out = np.full(len(points), np.nan)
    present = ~np.isnan(levels)
    if present.sum() < 2:
        return out
    rows = frame.loc[points[present]]
    r = stock_log_returns(rows, cfg.price_field)  # consecutive present rows
    pos = np.flatnonzero(present)
    consecutive = np.diff(pos) == 1  # previous present row is the previous grid point
    out[pos[1:][consecutive]] = r.to_numpy()[consecutive]
    # cross-check against the plain formula on the grid (identical by construction)
    ref = np.concatenate([[np.nan], log_returns(levels)])
    assert np.allclose(out, ref, equal_nan=True)
    return out


# ------------------------------------------------------------------ origins and targets
@dataclass
class PreparedOrigin:
    asset: str
    origin_ts: pd.Timestamp
    cutoff: datetime
    status: str  # 'ok' | 'excluded'
    reason: str | None
    target_timestamps: list[pd.Timestamp]  # one per configured horizon
    timestamps: np.ndarray | None = None  # (T,) datetime64[ns], naive UTC
    values: np.ndarray | None = None  # (T,) float64, NaN = missing
    future_timestamps: np.ndarray | None = None  # (max_horizon,)
    last_level: float | None = None  # price / probability at the origin
    last_value: float | None = None  # target-space value at the origin
    missing_points: int = 0
    input_hash: str | None = None
    provenance: dict = field(default_factory=dict)

    @property
    def context_start(self) -> str | None:
        return (
            None
            if self.timestamps is None
            else to_iso(pd.Timestamp(self.timestamps[0], tz="UTC").to_pydatetime())
        )

    @property
    def context_end(self) -> str | None:
        return (
            None
            if self.timestamps is None
            else to_iso(pd.Timestamp(self.timestamps[-1], tz="UTC").to_pydatetime())
        )


def input_hash(timestamps: np.ndarray, values: np.ndarray, cutoff: datetime, future: np.ndarray) -> str:
    h = hashlib.sha256()
    v = np.asarray(values, dtype=np.float64)
    h.update(np.isnan(v).tobytes())
    h.update(np.nan_to_num(v, nan=0.0).tobytes())
    h.update(np.asarray(timestamps).astype("datetime64[ns]").astype(np.int64).tobytes())
    h.update(np.asarray(future).astype("datetime64[ns]").astype(np.int64).tobytes())
    h.update(to_iso(cutoff).encode())
    return h.hexdigest()


def _naive(idx: pd.DatetimeIndex) -> np.ndarray:
    return idx.tz_convert("UTC").tz_localize(None).to_numpy().astype("datetime64[ns]")


def _provenance(df: pd.DataFrame, diag: dict, mode: KnowledgeMode) -> dict:
    p = dict(diag)
    if "knowledge" in df.columns:
        p["captured"] = int((df["knowledge"] == "captured").sum())
        p["reconstructed"] = int((df["knowledge"] == "reconstructed").sum())
    else:
        p["captured"], p["reconstructed"] = len(df), 0
    if len(df):
        p["max_version"] = int(df["version"].max())
        p["sources"] = sorted(df["source"].unique().tolist())
    p["knowledge_mode"] = KnowledgeMode(mode).value
    return p


class OriginBuilder:
    """Builds every origin's context and every realised target for one asset."""

    def __init__(self, session: Session, cfg: ExperimentConfig, grid: Grid):
        self.s = session
        self.cfg = cfg
        self.grid = grid
        self.mode = KnowledgeMode(cfg.knowledge_mode)
        self.latency = timedelta(seconds=cfg.extra_latency_seconds)
        self.ctx_points = cfg.context_length + (1 if cfg.target == "log_return" else 0)

    def _read(self, asset: ResearchAsset, as_of: datetime, start: datetime | None) -> pd.DataFrame:
        return read_history(self.s, self.mode, asset.asset_id, as_of, self.cfg.interval, self.cfg.source,
                            start=start, extra_latency=self.latency)  # fmt: skip

    def candidate_origins(self, asset: ResearchAsset, span: tuple[pd.Timestamp, pd.Timestamp] | None
                          ) -> tuple[list[pd.Timestamp], dict]:  # fmt: skip
        """Deterministic origins for one asset and counts of grid origins skipped as out of span."""
        cfg = self.cfg
        pts = self.grid.between(pd.Timestamp(cfg.origin_start), pd.Timestamp(cfg.origin_end))
        if cfg.domain == "stocks":
            cand = list(pts[:: cfg.origin_stride])
        else:
            hrs = np.asarray((pts - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(hours=1), dtype=np.int64)
            cand = list(pts[hrs % cfg.origin_stride == 0])  # aligned to UTC hours since the epoch
        skipped = {"outside_data_span": 0, "after_market_close": 0}
        out = []
        for t in cand:
            if span is None or t < span[0] or t > span[1]:
                skipped["outside_data_span"] += 1
                continue
            if cfg.respect_closing_time and asset.closing_time is not None and \
                    t + HOUR > pd.Timestamp(asset.closing_time):  # fmt: skip
                skipped["after_market_close"] += 1
                continue
            out.append(t)
        return out, skipped

    def prepare_origin(self, asset: ResearchAsset, t_o: pd.Timestamp) -> PreparedOrigin:
        cfg = self.cfg
        cutoff = (t_o + pd.Timedelta(seconds=cfg.cutoff_delay_seconds)).to_pydatetime()
        future = self.grid.after(t_o, cfg.max_horizon)
        tgt_ts = [future[h - 1] for h in cfg.horizons]
        po = PreparedOrigin(asset.key, t_o, cutoff, "excluded", None, tgt_ts)
        pts = self.grid.upto(t_o, self.ctx_points)
        df = self._read(asset, cutoff, pts[0].to_pydatetime())
        if (
            len(df) and (df["timestamp"] > pd.Timestamp(cutoff)).any()
        ):  # accessor contract; never trust blindly
            raise AssertionError("replay accessor returned an observation after the cutoff")
        gs = levels_on_grid(df, pts, cfg.price_field)
        po.provenance = _provenance(gs.frame, gs.diagnostics, self.mode)
        if gs.diagnostics["duplicate_timestamps"]:
            po.reason = "duplicate_timestamps"
            return po
        vals = target_values(cfg, gs.frame, gs.levels, pts)
        if cfg.target == "log_return":
            vals, ts = vals[1:], pts[1:]
        else:
            ts = pts
        if cfg.target == "logit_price":
            eps = cfg.logit_eps
            lv = gs.levels[~np.isnan(gs.levels)]
            po.provenance["clipped_probabilities"] = int(((lv <= eps) | (lv >= 1 - eps)).sum())
        if np.isnan(gs.levels[-1]) or np.isnan(vals[-1]):
            po.reason = "origin_observation_missing"
            return po
        n_valid = int((~np.isnan(vals)).sum())
        # gaps inside the observed span; a history that simply starts later is governed by
        # min_context_observations, not counted as missing
        first = int(np.argmax(~np.isnan(vals)))
        span = len(vals) - first
        missing = span - n_valid
        po.missing_points = missing
        if n_valid < cfg.min_context_observations:
            po.reason = "insufficient_context"
            return po
        if missing / span > cfg.max_missing_context_fraction:
            po.reason = "too_many_missing_context"
            return po
        # the context starts with an observation (leading points before the series began are dropped)
        po.values, po.timestamps = vals[first:], _naive(ts[first:])
        po.future_timestamps = _naive(future)
        po.last_level = float(gs.levels[-1])
        po.last_value = float(vals[-1])
        po.input_hash = input_hash(po.timestamps, po.values, cutoff, po.future_timestamps)
        po.status = "ok"
        return po

    def realised(self, asset: ResearchAsset, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Realised target values on the grid in [start, end], read at ``targets_as_of``.

        Columns: target_ts, value, level, status ('observed' | reason), available_at, version,
        knowledge. ``start`` should be one grid point before the first target so returns exist.
        """
        cfg = self.cfg
        pts = self.grid.between(start, end)
        if not len(pts):
            return pd.DataFrame(columns=["target_ts", "value", "level", "status", "available_at", "version",
                                         "knowledge"])  # fmt: skip
        df = self._read(asset, cfg.targets_as_of, pts[0].to_pydatetime())
        gs = levels_on_grid(df, pts, cfg.price_field)
        vals = target_values(cfg, gs.frame, gs.levels, pts)
        fr = gs.frame
        rows = []
        for i, t in enumerate(pts):
            v = vals[i]
            if not np.isnan(v):
                r = fr.loc[t]
                status = "observed"
                if (
                    cfg.respect_closing_time
                    and asset.closing_time is not None
                    and t > pd.Timestamp(asset.closing_time)
                ):
                    status, v = "after_market_close", np.nan
                rows.append([t, v, gs.levels[i], status, r["available_at"], int(r["version"]),
                             r["knowledge"] if "knowledge" in fr.columns else "captured"])  # fmt: skip
            else:
                known = t + pd.Timedelta(seconds=cfg.cutoff_delay_seconds) <= pd.Timestamp(cfg.targets_as_of)
                status = "target_missing" if known else "target_not_yet_available"
                if (
                    cfg.respect_closing_time
                    and asset.closing_time is not None
                    and t > pd.Timestamp(asset.closing_time)
                ):
                    status = "after_market_close"
                rows.append([t, np.nan, gs.levels[i], status, None, None, None])
        return pd.DataFrame(rows, columns=["target_ts", "value", "level", "status", "available_at", "version",
                                           "knowledge"])  # fmt: skip

    def data_span(self, asset: ResearchAsset) -> tuple[pd.Timestamp, pd.Timestamp] | None:
        """First and last stored timestamp visible at ``targets_as_of`` (bounds the origin loop)."""
        df = self._read(asset, self.cfg.targets_as_of, None)
        if df.empty:
            return None
        return df["timestamp"].min(), df["timestamp"].max()


def make_grid(cfg: ExperimentConfig, earliest: datetime) -> Grid:
    end = cfg.targets_as_of + (
        timedelta(days=60) if cfg.domain == "stocks" else timedelta(hours=cfg.max_horizon + 1)
    )
    if cfg.domain == "stocks":
        return stock_grid(cfg.calendar, earliest, end)
    return hourly_grid(earliest, end)


def json_ts(ts: list[pd.Timestamp]) -> str:
    return json.dumps([to_iso(t.to_pydatetime()) for t in ts])


# ------------------------------------------------------------------ asset listing (descriptive only)
def describe_assets(session: Session, domain: str, calendar: str = "XNYS") -> list[dict]:
    """Stored-row statistics per research asset, for ``mpe research assets``.

    Descriptive aggregates over stored rows (all versions collapsed to distinct timestamps). They
    choose nothing and feed no forecast: experiments read observations only through the replay
    accessors.
    """
    from sqlalchemy import func

    from mpe.storage.orm import DataQualityEvent, Observation

    if domain == "stocks":
        assets = session.scalars(select(Asset).where(Asset.provider == "yfinance").order_by(Asset.id)).all()
        source, interval = "yfinance", "1d"
    else:
        assets = session.scalars(select(Asset).where(Asset.provider == "polymarket", Asset.outcome_side == "YES")
                                 .order_by(Asset.id)).all()  # fmt: skip
        source, interval = "polymarket_clob_history", "1h"
    out = []
    for a in assets:
        r = session.execute(
            select(func.count(func.distinct(Observation.timestamp)), func.min(Observation.timestamp),
                   func.max(Observation.timestamp), func.sum(Observation.version > 1),
                   func.sum(Observation.close.is_(None)), func.min(Observation.retrieved_at),
                   func.max(Observation.retrieved_at))
            .where(Observation.asset_id == a.id, Observation.source == source, Observation.interval == interval)
        ).one()  # fmt: skip
        n, first, last, corrected, null_close, r_first, r_last = r
        item = {"key": a.symbol, "asset_id": a.id, "type": a.asset_type, "source": source, "interval": interval,
                "first": first if isinstance(first, str) or first is None else to_iso(first),
                "last": last if isinstance(last, str) or last is None else to_iso(last),
                "observations": int(n or 0), "corrected_rows": int(corrected or 0), "null_close": int(null_close or 0),
                "retrieved_first": r_first if isinstance(r_first, str) or r_first is None else to_iso(r_first),
                "retrieved_last": r_last if isinstance(r_last, str) or r_last is None else to_iso(r_last),
                "warnings": []}  # fmt: skip
        if domain == "polymarket" and a.market_id:
            m = session.get(Market, a.market_id)
            item.update(key=m.provider_market_id, label=m.question, status=m.resolution_status,
                        selected=bool(m.selected), closing_time=to_iso(m.closing_time) if m.closing_time else None)  # fmt: skip
            if not m.selected:
                item["warnings"].append("not in the selected panel")
        else:
            item["label"] = a.name or a.symbol
        if n and first and last:
            f, l_ = pd.Timestamp(item["first"]), pd.Timestamp(item["last"])
            if domain == "stocks" and a.asset_type in ("stock", "etf", "index"):
                g = stock_grid(calendar, f.to_pydatetime(), l_.to_pydatetime()).points
                expected = len(g)
                ts = session.scalars(select(func.distinct(Observation.timestamp)).where(
                    Observation.asset_id == a.id, Observation.source == source, Observation.interval == interval)).all()  # fmt: skip
                tsi = pd.DatetimeIndex([pd.Timestamp(t if isinstance(t, str) else to_iso(t)) for t in ts])
                off = int((~tsi.isin(g)).sum())
                item["usable_observations"] = int(tsi.isin(g).sum())
                item["missing_sessions"] = expected - item["usable_observations"]
                if off:
                    item["warnings"].append(
                        f"{off} rows off the {calendar} calendar (excluded by experiments)"
                    )
                if item["missing_sessions"]:
                    item["warnings"].append(f"{item['missing_sessions']} {calendar} sessions missing")
            elif domain == "stocks":
                item["usable_observations"] = 0
                item["warnings"].append(
                    f"{a.asset_type}: not on the {calendar} calendar; not supported by M2 stock experiments"
                )
            else:
                span_h = int((l_ - f) / HOUR) + 1
                item["usable_observations"] = int(n)
                item["missing_hours"] = span_h - int(n)
                if item["missing_hours"]:
                    item["warnings"].append(f"{item['missing_hours']} hourly samples missing in span")
        if null_close:
            item["warnings"].append(f"{null_close} rows without close")
        dq = session.execute(select(DataQualityEvent.check_name, func.count()).where(DataQualityEvent.asset_id == a.id)
                             .group_by(DataQualityEvent.check_name)).all()  # fmt: skip
        for name, c in dq:
            item["warnings"].append(f"quality events: {name} x{c}")
        out.append(item)
    return out
