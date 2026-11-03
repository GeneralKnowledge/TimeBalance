"""Offline fixtures for the M2 research laboratory: a small market database and fake models.

Nothing here needs network access, Timestral weights, a GPU or the user's database.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import ClassVar

import exchange_calendars as xc
import numpy as np
import pandas as pd

from mpe.clock import FixedClock
from mpe.config import Settings
from mpe.data.providers.base import Instrument, ObservationRecord
from mpe.data.providers.polymarket import SRC_HISTORY
from mpe.models.base import (
    DEFAULT_QUANTILE_LEVELS,
    ForecastInput,
    ForecastOutput,
    ModelMetadata,
    ModelNotLoaded,
    _to_ns,
    resolve_levels,
    truncate_context,
    validate_input,
)
from mpe.research.config import ModelSpec
from mpe.research.runner import default_model_factory
from mpe.research.store import ResearchStore, make_research_engine
from mpe.storage import repositories as R
from mpe.storage.database import make_engine, session_factory, upgrade
from mpe.storage.orm import Market, Resolution

BACKFILLED = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


def dec(x: float) -> Decimal:
    return Decimal(f"{x:.7g}")


def sessions(start: str, end: str) -> pd.DatetimeIndex:
    cal = xc.get_calendar("XNYS", start="2000-01-01")
    c = cal.closes
    c = c[(c.index >= pd.Timestamp(start)) & (c.index <= pd.Timestamp(end))]
    return pd.DatetimeIndex(c).tz_convert("UTC").rename(None)


def stock_records(symbol: str, closes: pd.DatetimeIndex, prices: np.ndarray, retrieved: datetime | None = None,
                  delay_min: int = 30) -> list[ObservationRecord]:  # fmt: skip
    out = []
    for t, p in zip(closes, prices, strict=True):
        ts = t.to_pydatetime()
        out.append(ObservationRecord(symbol=symbol, timestamp=ts, interval="1d", source="yfinance",
                                     retrieved_at=retrieved or BACKFILLED,
                                     available_at=ts + timedelta(minutes=delay_min),
                                     close=None if p is None else dec(p), adj_close=None if p is None else dec(p)))  # fmt: skip
    return out


def pm_records(token: str, hours: pd.DatetimeIndex, probs: np.ndarray, retrieved: datetime | None = None,
               offset_s: int = 20, latency_s: int = 60) -> list[ObservationRecord]:  # fmt: skip
    out = []
    for t, p in zip(hours, probs, strict=True):
        ts = t.to_pydatetime()
        st = ts + timedelta(seconds=offset_s)
        out.append(ObservationRecord(symbol=token, timestamp=ts, interval="1h", source=SRC_HISTORY,
                                     retrieved_at=retrieved or BACKFILLED, source_ts=st,
                                     available_at=st + timedelta(seconds=latency_s), close=dec(p)))  # fmt: skip
    return out


def random_walk(n: int, seed: int, start: float = 100.0, vol: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(rng.normal(0.0003, vol, n)))


class MarketDB:
    """A temporary market-data database with a couple of stocks and Polymarket markets."""

    def __init__(self, tmp_path):
        self.path = tmp_path / "market.sqlite3"
        self.engine = make_engine(self.path)
        upgrade(self.engine)
        self.factory = session_factory(self.engine)

    def add_stock(self, symbol: str, closes: pd.DatetimeIndex, prices, asset_type: str = "etf", **kw) -> int:
        with self.factory() as s:
            a = R.get_or_create_asset(s, Instrument(symbol, "yfinance", asset_type))
            R.write_observations(s, a.id, stock_records(symbol, closes, prices, **kw))
            s.commit()
            return a.id

    def add_stock_records(self, symbol: str, recs: list[ObservationRecord]) -> None:
        with self.factory() as s:
            a = R.asset_by_symbol(s, "yfinance", symbol)
            R.write_observations(s, a.id, recs)
            s.commit()

    def add_market(self, cid: str, hours: pd.DatetimeIndex, probs, *, closing: datetime | None = None,
                   outcome: str | None = None, resolved_at: datetime | None = None, no_probs=None, **kw) -> int:  # fmt: skip
        with self.factory() as s:
            m = Market(provider="polymarket", provider_market_id=cid, question=f"Question {cid}?",
                       market_type="binary", resolution_status="resolved" if outcome else "open",
                       yes_token_id=f"{cid}-yes", no_token_id=f"{cid}-no", closing_time=closing, selected=1,
                       selection_reason="selected: test", first_seen_at=BACKFILLED, updated_at=BACKFILLED)  # fmt: skip
            s.add(m)
            s.flush()
            yes = R.get_or_create_asset(s, Instrument(f"{cid}-yes", "polymarket", "pm_token", outcome_side="YES"),
                                        market_id=m.id)  # fmt: skip
            no = R.get_or_create_asset(s, Instrument(f"{cid}-no", "polymarket", "pm_token", outcome_side="NO"),
                                       market_id=m.id)  # fmt: skip
            R.write_observations(s, yes.id, pm_records(f"{cid}-yes", hours, probs, **kw))
            nop = no_probs if no_probs is not None else 1 - np.asarray(probs)
            R.write_observations(s, no.id, pm_records(f"{cid}-no", hours, nop, **kw))
            if outcome:
                s.add(Resolution(market_id=m.id, resolved_at=resolved_at or closing, outcome=outcome,
                                 source="test", retrieved_at=BACKFILLED))  # fmt: skip
            s.commit()
            return yes.id


def research_store(tmp_path) -> ResearchStore:
    return ResearchStore(make_research_engine(tmp_path / "research.sqlite3"))


def settings() -> Settings:
    return Settings()


def clock() -> FixedClock:
    return FixedClock(NOW)


# ------------------------------------------------------------------ fake models
class FakeTimestral:
    """Deterministic stand-in for a Timestral size: median = shrunk mean of the context, quantiles
    from the context's empirical spread. Records load/unload calls and every input it saw."""

    loads: ClassVar[list[str]] = []
    unloads: ClassVar[list[str]] = []
    resident: ClassVar[set[str]] = set()

    def __init__(self, name: str, shrink: float = 0.5, fail_on: set | None = None, bad_output_on: set | None = None,
                 version: str = "fake-rev-1"):  # fmt: skip
        self.name = name
        self.shrink = shrink
        self.fail_on = fail_on or set()
        self.bad_output_on = bad_output_on or set()
        self.version = version
        self._loaded = False
        self.seen: list[ForecastInput] = []

    def load(self, device: str = "auto") -> None:
        FakeTimestral.loads.append(self.name)
        FakeTimestral.resident.add(self.name)
        assert len(FakeTimestral.resident) == 1, f"two models resident: {FakeTimestral.resident}"
        self._loaded = True

    def unload(self) -> None:
        FakeTimestral.unloads.append(self.name)
        FakeTimestral.resident.discard(self.name)
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(self.name, "timestral", self.name.split("-")[1].upper(), self.version, True, True, True,
                             4096, 1024)  # fmt: skip

    def forecast(self, data: ForecastInput) -> ForecastOutput:
        if not self._loaded:
            raise ModelNotLoaded(self.name)
        meta = self.metadata()
        validate_input(data, meta)
        self.seen.append(data)
        cutoff = np.datetime64(data.input_cutoff.astimezone(UTC).replace(tzinfo=None), "ns")
        assert (np.asarray(data.timestamps).astype("datetime64[ns]") <= cutoff).all()
        ctx = truncate_context(data, meta.max_context)
        key = str(pd.Timestamp(data.input_cutoff).floor("h"))
        if key in self.fail_on:
            raise RuntimeError("simulated model failure")
        x = ctx.values[0]
        x = x[~np.isnan(x)]
        levels = resolve_levels(data.quantile_levels, DEFAULT_QUANTILE_LEVELS)
        med = np.full(data.horizon, self.shrink * x[-20:].mean() + (1 - self.shrink) * x[-1])
        spread = np.quantile(x - x.mean(), levels)
        q = med[:, None] + spread[None, :] * np.sqrt(np.arange(1, data.horizon + 1))[:, None]
        if key in self.bad_output_on:
            q = q[:, ::-1]  # decreasing quantiles: must fail validate_output
        return ForecastOutput(values=med[None, :], timestamps=_to_ns(data.future_timestamps),
                              quantile_levels=tuple(levels), quantiles=q[None], model=meta,
                              inference_ms=0.1, device="cpu", input_window=ctx.input_window)  # fmt: skip


def fake_factory(**per_model) -> callable:
    """Model factory: Timestral specs become FakeTimestral, baselines are the real M0 classes."""
    FakeTimestral.loads, FakeTimestral.unloads, FakeTimestral.resident = [], [], set()

    def make(spec: ModelSpec):
        if spec.family == "timestral":
            return FakeTimestral(spec.name, **per_model.get(spec.name, {}))
        return default_model_factory(spec)

    return make


def perf() -> float:
    return time.perf_counter()
