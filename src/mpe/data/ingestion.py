"""Backfill and incremental update orchestration.

Unit of work: one instrument (or the market panel). All network calls for a unit happen first;
then the unit is written in a single transaction. A provider failure (timeout, 429 after
retries, malformed JSON) therefore leaves the database exactly as it was for that unit; the
failure is reported in the job's stats instead.
"""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from mpe.clock import Clock, from_iso, to_iso
from mpe.config import AssetsConfig, Settings
from mpe.data import validation as V
from mpe.data.normalisation import normalise
from mpe.data.providers.base import Instrument, ObservationRecord, ProviderError, QualityIssue
from mpe.data.providers.polymarket import (
    SRC_HISTORY,
    SRC_TRADES,
    MarketInfo,
    PolymarketProvider,
    resolved_at,
    select_markets,
    token_instruments,
)
from mpe.data.providers.yahoo import SOURCE as YAHOO_SOURCE
from mpe.data.providers.yahoo import YahooProvider
from mpe.storage import repositories as R
from mpe.storage.database import transaction
from mpe.storage.orm import Asset, DataQualityEvent, JobRun, Market, Observation

log = logging.getLogger(__name__)


@dataclass
class UnitResult:
    unit: str
    ok: bool
    stats: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class RunReport:
    results: list[UnitResult] = field(default_factory=list)

    def add(self, r: UnitResult) -> None:
        self.results.append(r)
        level = logging.INFO if r.ok else logging.ERROR
        log.log(level, "%s %s %s", r.unit, "ok" if r.ok else f"FAILED: {r.error}", r.stats)

    @property
    def failed(self) -> list[UnitResult]:
        return [r for r in self.results if not r.ok]

    def as_dict(self) -> dict:
        return {
            "units": len(self.results),
            "failed": len(self.failed),
            "results": [{"unit": r.unit, "ok": r.ok, "error": r.error, **r.stats} for r in self.results],
        }


class RawDump:
    """Append raw provider payloads to one gzip JSONL file per run (audit trail; gitignored)."""

    def __init__(self, directory: Path, clock: Clock, provider: str):
        directory.mkdir(parents=True, exist_ok=True)
        stamp = clock.now().strftime("%Y%m%dT%H%M%SZ")
        self.path = directory / f"{provider}_{stamp}.jsonl.gz"
        self._fh = gzip.open(self.path, "at")  # noqa: SIM115 - open for the whole run, closed in close()
        self.clock = clock

    def __call__(self, url: str, params: dict, data) -> None:
        self._fh.write(
            json.dumps({"t": to_iso(self.clock.now()), "url": url, "params": params, "data": data}) + "\n"
        )

    def close(self) -> None:
        self._fh.close()


class Ingestor:
    def __init__(
        self,
        settings: Settings,
        assets: AssetsConfig,
        clock: Clock,
        factory: sessionmaker[Session],
        yahoo: YahooProvider | None = None,
        polymarket: PolymarketProvider | None = None,
    ):
        self.settings = settings
        self.assets = assets
        self.clock = clock
        self.factory = factory
        self.yahoo = yahoo
        self.pm = polymarket

    # ============================================================ stocks
    def _stock_unit(self, inst: Instrument, start: datetime, end: datetime, full: bool) -> UnitResult:
        unit = f"yfinance:{inst.symbol}"
        try:
            recs = self.yahoo.fetch_history(inst, start, end)
        except ProviderError as e:
            return UnitResult(unit, False, error=str(e))
        recs, issues = normalise(recs)
        if full and not recs:
            return UnitResult(unit, False, error="no bars returned for a backfill")
        issues += V.check_timestamps(recs) + V.check_ohlc(recs)
        issues += V.check_outliers(recs, self.settings.stocks.outlier_z)
        if inst.asset_type != "fx" and recs:
            issues += V.check_missing_sessions(recs, self.yahoo.calendar)
        elif recs:
            issues += V.check_gaps(recs, timedelta(days=1), min_gap_steps=5)
        now = self.clock.now()
        with transaction(self.factory) as s:
            asset = R.get_or_create_asset(s, inst)
            if (
                recs
                and asset.listed_at is None
                and full
                and recs[0].timestamp.date().isoformat() > self.settings.stocks.backfill_start
            ):
                asset.listed_at = recs[0].timestamp  # first bar after our start date: listing (or data start)
            ws = R.write_observations(s, asset.id, recs)
            nq = R.add_quality_events(s, issues, now, asset_id=asset.id)
        stats = {**ws.as_dict(), "fetched": len(recs), "quality_events": nq}
        if recs:
            stats["first"], stats["last"] = to_iso(recs[0].timestamp), to_iso(recs[-1].timestamp)
        return UnitResult(unit, True, stats)

    def backfill_stocks(self, symbols: Sequence[str] | None = None) -> RunReport:
        rep = RunReport()
        start = datetime.fromisoformat(self.settings.stocks.backfill_start + "T00:00:00+00:00")
        for inst in self._stock_instruments(symbols):
            rep.add(self._stock_unit(inst, start, self.clock.now(), full=True))
        return rep

    def update_stocks(self, symbols: Sequence[str] | None = None, overlap_days: int = 10) -> RunReport:
        """Fetch recent bars. The overlap re-reads bars we already have, so Yahoo corrections
        become new versions instead of being missed."""
        rep = RunReport()
        now = self.clock.now()
        for inst in self._stock_instruments(symbols):
            with self.factory() as s:
                a = R.asset_by_symbol(s, inst.provider, inst.symbol)
                last = R.latest_timestamp(s, a.id, "1d", YAHOO_SOURCE) if a else None
            if last is None:
                start = datetime.fromisoformat(self.settings.stocks.backfill_start + "T00:00:00+00:00")
                rep.add(self._stock_unit(inst, start, now, full=True))
            else:
                rep.add(self._stock_unit(inst, last - timedelta(days=overlap_days), now, full=False))
        return rep

    def _stock_instruments(self, symbols):
        insts = list(self.yahoo.list_instruments())
        if symbols:
            want = set(symbols)
            insts = [i for i in insts if i.symbol in want]
        return insts

    # ============================================================ polymarket: market panel
    def refresh_markets(self) -> UnitResult:
        unit = "polymarket:markets"
        now = self.clock.now()
        try:
            open_, closed = self.pm.discover()
            with self.factory() as s:
                already = {m.provider_market_id for m in R.selected_markets(s)}
            seen = {m.condition_id for m in [*open_, *closed]}
            missing = sorted(already - seen)
            if missing:  # panel members that fell out of today's scan: refresh them by id
                for m in self.pm.fetch_markets_by_condition(missing):
                    (closed if m.closed else open_).append(m)
            decisions = select_markets(open_, closed, self.settings.polymarket, now, already)
            chosen = [d.market for d in decisions if d.selected]
            resolved = [m for m in chosen if m.resolution_status == "resolved"]
            res_raw = self.pm.fetch_resolutions([m.condition_id for m in resolved]) if resolved else {}
        except ProviderError as e:
            return UnitResult(unit, False, error=str(e))
        with transaction(self.factory) as s:
            n_sel = 0
            for d in decisions:
                row = R.upsert_market(s, d.market, d.selected, d.reason, now)
                if d.selected or row.selected:
                    n_sel += 1
                    for inst in token_instruments(d.market):
                        R.get_or_create_asset(s, inst, market_id=row.id)
                    if d.market.resolution_status == "resolved" and d.market.resolution_value:
                        R.upsert_resolution(
                            s, row, d.market.resolution_value, resolved_at(d.market, res_raw.get(d.market.condition_id)),
                            "gamma+data_v2_resolutions", now, res_raw.get(d.market.condition_id),
                        )  # fmt: skip
                    if d.market.closed:
                        for a in s.scalars(select(Asset).where(Asset.market_id == row.id)):
                            a.active = 0
                            a.delisted_at = a.delisted_at or d.market.closed_time or d.market.closing_time
        return UnitResult(unit, True, {"candidates": len(decisions), "selected": n_sel,
                                       "resolved_selected": len(resolved)})  # fmt: skip

    # ============================================================ polymarket: history, trades, books
    def _pm_history_unit(self, market: Market, asset: Asset, full: bool) -> UnitResult:
        unit = f"polymarket:{asset.outcome_side}:{(market.slug or market.provider_market_id)[:60]}"
        now = self.clock.now()
        inst = Instrument(symbol=asset.symbol, provider="polymarket", asset_type="pm_token",
                          outcome_side=asset.outcome_side, market_key=market.provider_market_id)  # fmt: skip
        with self.factory() as s:
            last = R.latest_timestamp(s, asset.id, "1h", SRC_HISTORY)
        opened = market.opening_time or (now - timedelta(days=30))
        end_cap = (market.closing_time or now) if market.resolution_status != "open" else now
        # closed markets: read a little past the close so the last trades are included
        end = (
            min(now, max(end_cap, opened) + timedelta(days=2)) if market.resolution_status != "open" else now
        )
        if last is not None and not full:
            if market.resolution_status != "open" and last >= end - timedelta(hours=2):
                return UnitResult(unit, True, {"skipped": "closed market already complete"})
            start = last - timedelta(hours=6)  # small overlap: catch late corrections
        else:
            start = opened
        try:
            recs = self.pm.fetch_history(inst, start, end)
        except ProviderError as e:
            return UnitResult(unit, False, error=str(e))
        recs, issues = normalise(recs)
        issues += V.check_timestamps(recs) + V.check_probability_bounds(recs)
        issues += V.check_gaps(recs, timedelta(hours=1), min_gap_steps=6)
        issues += V.check_outliers(recs, self.settings.stocks.outlier_z, use_logit=True)
        with transaction(self.factory) as s:
            ws = R.write_observations(s, asset.id, recs)
            nq = R.add_quality_events(s, issues, now, asset_id=asset.id)
        return UnitResult(unit, True, {**ws.as_dict(), "fetched": len(recs), "quality_events": nq})

    def _pm_trades_unit(self, market: Market, assets: list[Asset]) -> UnitResult:
        unit = f"polymarket:trades:{(market.slug or market.provider_market_id)[:60]}"
        try:
            recs = self.pm.fetch_hourly_trade_volume(market.provider_market_id, [a.symbol for a in assets])
        except ProviderError as e:
            return UnitResult(unit, False, error=str(e))
        recs, issues = normalise(recs)
        by_symbol = {a.symbol: a for a in assets}
        stats = R.WriteStats()
        with transaction(self.factory) as s:
            for sym, asset in by_symbol.items():
                stats += R.write_observations(s, asset.id, [r for r in recs if r.symbol == sym])
            R.add_quality_events(s, issues, self.clock.now())
        return UnitResult(unit, True, {**stats.as_dict(), "hours": len(recs)})

    def _pm_book_unit(self, market: Market, assets: list[Asset]) -> UnitResult:
        unit = f"polymarket:book:{(market.slug or market.provider_market_id)[:60]}"
        try:
            books = [(a, self.pm.fetch_order_book(a.symbol)) for a in assets]
        except ProviderError as e:
            return UnitResult(unit, False, error=str(e))
        liq = None
        try:
            liq = json.loads(market.raw_json or "{}").get("liquidityNum")
        except json.JSONDecodeError:
            pass
        from mpe.storage.types import to_decimal

        now = self.clock.now()
        n = 0
        with transaction(self.factory) as s:
            for asset, book in books:
                R.write_book_snapshot(s, asset.id, book)
                snap = self.pm.snapshot_from_book(
                    book, liquidity=to_decimal(liq) if liq is not None else None
                )
                issues = V.check_probability_bounds([snap])
                if "crossed_book" in snap.quality_flags or "empty_book" in snap.quality_flags:
                    issues.append(QualityIssue("book_" + ("crossed" if "crossed_book" in snap.quality_flags else "empty"),
                                               "warning", {"token": asset.symbol}, source=snap.source))  # fmt: skip
                R.write_observations(s, asset.id, [snap])
                R.add_quality_events(s, issues, now, asset_id=asset.id)
                n += 1
        return UnitResult(unit, True, {"books": n})

    def _panel(self) -> list[tuple[Market, list[Asset]]]:
        with self.factory() as s:
            out = []
            for m in R.selected_markets(s):
                assets = list(
                    s.scalars(
                        select(Asset).where(Asset.market_id == m.id).order_by(Asset.outcome_side.desc())
                    )
                )
                out.append((m, assets))
            return out

    def sync_polymarket(self, full: bool, books: bool, trades: bool = True) -> RunReport:
        rep = RunReport()
        rep.add(self.refresh_markets())
        for market, assets in self._panel():
            for a in assets:
                rep.add(self._pm_history_unit(market, a, full=full))
            if trades and market.resolution_status == "open":
                rep.add(self._pm_trades_unit(market, assets))
            if books and market.resolution_status == "open":
                rep.add(self._pm_book_unit(market, assets))
        return rep

    def backfill_polymarket(self) -> RunReport:
        return self.sync_polymarket(full=False, books=True)  # incremental: resumes where it stopped

    def update_polymarket(self) -> RunReport:
        return self.sync_polymarket(full=False, books=True)


# ================================================================ health report
def health_report(settings: Settings, factory: sessionmaker[Session], clock: Clock, calendar=None) -> dict:
    now = clock.now()
    out: dict = {"generated_at": to_iso(now), "assets": [], "markets": {}, "quality": {}, "jobs": []}
    with factory() as s:
        rows = s.execute(
            select(Asset.id, Asset.provider, Asset.symbol, Asset.asset_type, Asset.active, Asset.name,
                   Observation.interval, Observation.source, func.count(Observation.id),
                   func.min(Observation.timestamp), func.max(Observation.timestamp))
            .join(Observation, Observation.asset_id == Asset.id, isouter=True)
            .group_by(Asset.id, Observation.interval, Observation.source)
            .order_by(Asset.provider.desc(), Asset.id)
        ).all()  # fmt: skip
        for aid, prov, sym, typ, active, name, interval, source, n, first, last in rows:
            first = to_iso(first) if isinstance(first, datetime) else first
            last = to_iso(last) if isinstance(last, datetime) else last
            last_dt = from_iso(last) if last else None
            item = {"asset_id": aid, "provider": prov, "symbol": sym if prov != "polymarket" else sym[:12] + "…",
                    "name": (name or "")[:70], "type": typ, "active": bool(active), "interval": interval,
                    "source": source, "rows": n, "first": first if isinstance(first, str) else None,
                    "last": last if isinstance(last, str) else None, "stale": None}  # fmt: skip
            if last_dt and active:
                if typ in ("stock", "etf", "index") and calendar is not None:
                    behind = V.sessions_since(calendar, last_dt, now - timedelta(
                        minutes=settings.availability.stock_close_delay_minutes))  # fmt: skip
                    item["stale"] = behind > settings.stocks.stale_after_sessions
                    item["sessions_behind"] = behind
                elif typ == "pm_token" and interval == "1h" and source == SRC_HISTORY:
                    hours = (now - last_dt).total_seconds() / 3600
                    item["stale"] = hours > 6
                    item["hours_behind"] = round(hours, 1)
            out["assets"].append(item)
        out["markets"] = {
            "stored": s.scalar(select(func.count(Market.id))),
            "selected": s.scalar(select(func.count(Market.id)).where(Market.selected == 1)),
            "selected_open": s.scalar(select(func.count(Market.id)).where(Market.selected == 1,
                                                                         Market.resolution_status == "open")),
            "selected_resolved": s.scalar(select(func.count(Market.id)).where(
                Market.selected == 1, Market.resolution_status == "resolved")),
        }  # fmt: skip
        since = to_iso(now - timedelta(days=7))
        q = s.execute(
            select(DataQualityEvent.check_name, DataQualityEvent.severity, func.count(DataQualityEvent.id))
            .where(DataQualityEvent.created_at >= since)
            .group_by(DataQualityEvent.check_name, DataQualityEvent.severity)
        ).all()
        out["quality"] = {f"{c} ({sev})": n for c, sev, n in q}
        for j in s.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(10)):
            out["jobs"].append({"id": j.id, "job": j.job_name, "scheduled_for": j.scheduled_for,
                                "status": j.status, "started": to_iso(j.started_at),
                                "error": (j.error or "")[:200] or None})  # fmt: skip
    return out


__all__ = [
    "SRC_TRADES",
    "Ingestor",
    "MarketInfo",
    "ObservationRecord",
    "RawDump",
    "RunReport",
    "UnitResult",
    "health_report",
]  # fmt: skip
