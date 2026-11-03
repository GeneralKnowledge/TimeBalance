"""Data access for ingestion and the strict point-in-time history accessor.

Reconstructed (backfill-based) replay lives separately in :mod:`mpe.storage.replay`.

Observations are append-only: a value that differs from the stored latest version is written as
a new row with ``version + 1``; an identical value is skipped, so re-running ingestion is a no-op.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Self

import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mpe.clock import Clock, to_iso
from mpe.data.providers.base import (
    BudgetExhausted,
    Instrument,
    ObservationRecord,
    OrderBookRecord,
    QualityIssue,
)
from mpe.storage.orm import (
    Asset,
    DataQualityEvent,
    JobRun,
    Market,
    Observation,
    OrderBookSnapshot,
    Resolution,
    SystemState,
)
from mpe.storage.types import canonical


# ------------------------------------------------------------------ assets and markets
def get_or_create_asset(session: Session, inst: Instrument, market_id: int | None = None) -> Asset:
    asset = session.scalar(select(Asset).where(Asset.provider == inst.provider, Asset.symbol == inst.symbol))
    meta = json.dumps(inst.meta, sort_keys=True) if inst.meta else None
    if asset is None:
        asset = Asset(
            symbol=inst.symbol, name=inst.name, asset_type=inst.asset_type, exchange=inst.exchange,
            currency=inst.currency, provider=inst.provider, market_id=market_id,
            outcome_side=inst.outcome_side, active=1, meta_json=meta,
        )  # fmt: skip
        session.add(asset)
        session.flush()
        return asset
    # descriptive fields may be refreshed; identity (provider, symbol, type) never changes
    if inst.name and asset.name != inst.name:
        asset.name = inst.name
    if market_id is not None and asset.market_id != market_id:
        asset.market_id = market_id
    if meta and asset.meta_json != meta:
        asset.meta_json = meta
    return asset


def upsert_market(session: Session, info, selected: bool, reason: str, now: datetime) -> Market:
    """Store a Polymarket market (``info`` is a ``MarketInfo``); selected or not (survivorship)."""
    row = session.scalar(
        select(Market).where(Market.provider == "polymarket", Market.provider_market_id == info.condition_id)
    )
    fields = dict(  # noqa: C408
        slug=info.slug, question=info.question, description=info.description,
        market_type="binary" if info.is_binary else f"{len(info.outcomes)}-outcome",
        category=info.category, event_id=info.event_id, event_slug=info.event_slug,
        neg_risk=int(info.neg_risk), yes_token_id=info.yes_token_id, no_token_id=info.no_token_id,
        resolution_rules=info.description, resolution_source=info.resolution_source,
        opening_time=info.opening_time, closing_time=info.closing_time,
        resolution_status=info.resolution_status, resolution_value=info.resolution_value,
        fee_bps=info.fee_bps, raw_json=json.dumps(info.raw, sort_keys=True), updated_at=now,
    )  # fmt: skip
    if row is None:
        row = Market(provider="polymarket", provider_market_id=info.condition_id, first_seen_at=now,
                     selected=int(selected), selection_reason=reason, **fields)  # fmt: skip
        session.add(row)
        session.flush()
        return row
    for k, v in fields.items():
        setattr(row, k, v)
    if selected:
        row.selected, row.selection_reason = 1, reason
    elif not row.selected:
        row.selection_reason = reason
    # a market selected in an earlier run stays in the panel with its original reason
    return row


def selected_markets(session: Session) -> list[Market]:
    return list(session.scalars(select(Market).where(Market.selected == 1).order_by(Market.id)))


def upsert_resolution(session: Session, market: Market, outcome: str, resolved_at: datetime,
                      source: str, retrieved_at: datetime, raw: dict | None) -> tuple[Resolution, bool]:  # fmt: skip
    row = session.scalar(select(Resolution).where(Resolution.market_id == market.id))
    raw_json = json.dumps(raw, sort_keys=True) if raw else None
    if row is None:
        row = Resolution(market_id=market.id, resolved_at=resolved_at, outcome=outcome, source=source,
                         retrieved_at=retrieved_at, raw_json=raw_json)  # fmt: skip
        session.add(row)
        return row, True
    changed = row.outcome != outcome
    if changed:  # should never happen; keep the evidence and flag it loudly
        add_quality_events(session, [QualityIssue(
            "resolution_changed", "error",
            {"market": market.provider_market_id, "old": row.outcome, "new": outcome}, source=source,
        )], retrieved_at)  # fmt: skip
        row.outcome, row.resolved_at, row.retrieved_at, row.raw_json = (
            outcome,
            resolved_at,
            retrieved_at,
            raw_json,
        )
    return row, changed


# ------------------------------------------------------------------ observations
@dataclass
class WriteStats:
    inserted: int = 0
    unchanged: int = 0
    corrected: int = 0

    def __iadd__(self, other: WriteStats) -> Self:
        self.inserted += other.inserted
        self.unchanged += other.unchanged
        self.corrected += other.corrected
        return self

    def as_dict(self) -> dict:
        return {"inserted": self.inserted, "unchanged": self.unchanged, "corrected": self.corrected}


def _same(a, b, rel_tol: Decimal | None = None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if rel_tol is not None and a != b:
        return abs(a - b) <= rel_tol * max(abs(a), abs(b))
    return a == b  # Decimal('1.50') == Decimal('1.5')


# Source noise that is not a correction. Yahoo recomputes adj_close on every request and the
# 7th significant digit wobbles (84.5923 vs 84.59229); a real dividend re-adjustment moves it by
# far more than 1e-5 relative.
SOURCE_TOLERANCES: dict[str, dict[str, Decimal]] = {"yfinance": {"adj_close": Decimal("1e-5")}}


def write_observations(session: Session, asset_id: int, records: Sequence[ObservationRecord]) -> WriteStats:
    stats = WriteStats()
    if not records:
        return stats
    groups: dict[tuple[str, str], list[ObservationRecord]] = {}
    for r in records:
        groups.setdefault((r.interval, r.source), []).append(r)
    for (interval, source), recs in groups.items():
        lo = min(r.timestamp for r in recs)
        hi = max(r.timestamp for r in recs)
        latest_v = (
            select(Observation.timestamp, func.max(Observation.version).label("v"))
            .where(Observation.asset_id == asset_id, Observation.interval == interval,
                   Observation.source == source, Observation.timestamp >= to_iso(lo),
                   Observation.timestamp <= to_iso(hi))
            .group_by(Observation.timestamp)
            .subquery()
        )  # fmt: skip
        existing = {
            o.timestamp: o
            for o in session.scalars(
                select(Observation).join(
                    latest_v,
                    and_(Observation.timestamp == latest_v.c.timestamp, Observation.version == latest_v.c.v),
                ).where(Observation.asset_id == asset_id, Observation.interval == interval,
                        Observation.source == source)
            )
        }  # fmt: skip
        seen: set[datetime] = set()
        for r in recs:
            if r.timestamp in seen:
                continue  # duplicates inside one batch are reported by validation, stored once
            seen.add(r.timestamp)
            old = existing.get(r.timestamp)
            tol = SOURCE_TOLERANCES.get(source, {})
            if old is not None and all(_same(getattr(old, k), v, tol.get(k)) for k, v in r.values().items()):
                stats.unchanged += 1
                continue
            version = 1 if old is None else old.version + 1
            session.add(Observation(
                asset_id=asset_id, timestamp=r.timestamp, interval=r.interval, source=r.source,
                source_ts=r.source_ts, retrieved_at=r.retrieved_at, available_at=r.available_at,
                version=version, quality_flags=json.dumps(list(r.quality_flags)) if r.quality_flags else None,
                **r.values(),
            ))  # fmt: skip
            if old is None:
                stats.inserted += 1
            else:
                stats.corrected += 1
    session.flush()
    return stats


def write_book_snapshot(session: Session, asset_id: int, book: OrderBookRecord) -> OrderBookSnapshot:
    def enc(levels):
        return json.dumps([[canonical(p), canonical(s)] for p, s in levels])

    snap = OrderBookSnapshot(asset_id=asset_id, timestamp=book.timestamp, retrieved_at=book.retrieved_at,
                             bids_json=enc(book.bids), asks_json=enc(book.asks))  # fmt: skip
    session.add(snap)
    return snap


def add_quality_events(session: Session, issues: Iterable[QualityIssue], now: datetime,
                       asset_id: int | None = None) -> int:  # fmt: skip
    n = 0
    for i in issues:
        session.add(DataQualityEvent(created_at=now, asset_id=asset_id, source=i.source,
                                     check_name=i.check_name, severity=i.severity,
                                     details_json=json.dumps(i.details, sort_keys=True, default=str)))  # fmt: skip
        n += 1
    return n


# ------------------------------------------------------------------ point-in-time accessor
SERIES = ("open", "high", "low", "close", "adj_close", "volume", "trade_count",
          "bid", "ask", "bid_size", "ask_size", "liquidity")  # fmt: skip


def get_history(
    session: Session,
    asset_id: int,
    as_of: datetime,
    interval: str,
    source: str | None = None,
    start: datetime | None = None,
) -> pd.DataFrame:
    """Everything known about an asset at ``as_of`` and nothing more.

    Keeps rows with ``available_at <= as_of`` and ``retrieved_at <= as_of``; for each
    (timestamp, source) returns the highest such version, so a later correction is invisible to a
    decision made before it was fetched. This is strict point-in-time replay: rows backfilled
    after ``as_of`` are excluded even if they describe earlier events. For research on backfilled
    data use :func:`mpe.storage.replay.get_reconstructed_history`, which is labelled as such.
    These two are the only sanctioned read paths for history.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware UTC")
    cut = to_iso(as_of)
    conds = [Observation.asset_id == asset_id, Observation.interval == interval,
             Observation.available_at <= cut, Observation.retrieved_at <= cut]  # fmt: skip
    if source is not None:
        conds.append(Observation.source == source)
    if start is not None:
        conds.append(Observation.timestamp >= to_iso(start))
    best = (
        select(Observation.timestamp, Observation.source, func.max(Observation.version).label("v"))
        .where(*conds)
        .group_by(Observation.timestamp, Observation.source)
        .subquery()
    )
    rows = session.scalars(
        select(Observation)
        .join(best, and_(Observation.timestamp == best.c.timestamp, Observation.source == best.c.source,
                         Observation.version == best.c.v))
        .where(Observation.asset_id == asset_id, Observation.interval == interval)
        .order_by(Observation.timestamp, Observation.source)
    ).all()  # fmt: skip
    cols = ["timestamp", "source", "version", "available_at", *SERIES]
    data = [[getattr(o, c) for c in cols] for o in rows]
    df = pd.DataFrame(data, columns=cols)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["available_at"] = pd.to_datetime(df["available_at"], utc=True)
    df.attrs["knowledge_mode"] = "strict_point_in_time"  # == replay.KnowledgeMode.STRICT
    return df


def asset_by_symbol(session: Session, provider: str, symbol: str) -> Asset | None:
    return session.scalar(select(Asset).where(Asset.provider == provider, Asset.symbol == symbol))


def latest_timestamp(session: Session, asset_id: int, interval: str, source: str) -> datetime | None:
    from mpe.clock import from_iso

    v = session.execute(
        select(func.max(Observation.timestamp)).where(
            Observation.asset_id == asset_id, Observation.interval == interval, Observation.source == source
        )
    ).scalar()
    # an aggregate bypasses the column TypeDecorator, so this comes back as ISO text
    return v if isinstance(v, datetime) or v is None else from_iso(v)


# ------------------------------------------------------------------ system state, jobs, budget
def get_state(session: Session, key: str) -> str | None:
    row = session.get(SystemState, key)
    return None if row is None else row.value


def set_state(session: Session, key: str, value: str, now: datetime) -> None:
    row = session.get(SystemState, key)
    if row is None:
        session.add(SystemState(key=key, value=value, updated_at=now))
    else:
        row.value, row.updated_at = value, now


class DbRequestBudget:
    """Daily request budget per provider, persisted in ``system_state`` in its own transactions
    so the count survives a rolled-back ingestion and a restart. Flushed every ``flush_every``."""

    def __init__(
        self, factory: sessionmaker[Session], clock: Clock, limits: dict[str, int], flush_every: int = 25
    ):
        self.factory = factory
        self.clock = clock
        self.limits = limits
        self.flush_every = flush_every
        self._pending: dict[str, int] = {}
        self._base: dict[str, tuple[str, int]] = {}

    def _key(self, provider: str) -> str:
        return f"request_budget:{provider}:{self.clock.now().strftime('%Y-%m-%d')}"

    def used(self, provider: str) -> int:
        key = self._key(provider)
        base = self._base.get(provider)
        if base is None or base[0] != key:
            with self.factory() as s:
                v = get_state(s, key)
            base = (key, int(v) if v else 0)
            self._base[provider] = base
            self._pending[provider] = 0
        return base[1] + self._pending.get(provider, 0)

    def consume(self, provider: str, n: int = 1) -> None:
        used = self.used(provider)
        limit = self.limits.get(provider)
        if limit is not None and used + n > limit:
            self.flush()
            raise BudgetExhausted(f"{provider}: daily request budget {limit} spent ({used} used)")
        self._pending[provider] = self._pending.get(provider, 0) + n
        if self._pending[provider] >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        for provider, n in list(self._pending.items()):
            if not n:
                continue
            key, base = self._base[provider]
            with self.factory() as s:
                set_state(s, key, str(base + n), self.clock.now())
                s.commit()
            self._base[provider] = (key, base + n)
            self._pending[provider] = 0


class JobAlreadyDone(RuntimeError):
    pass


def start_job(factory: sessionmaker[Session], name: str, scheduled_for: str, now: datetime) -> int:
    """Claim (job_name, scheduled_for). A succeeded run is never repeated; a failed or abandoned
    one is retried in place, so the uniqueness constraint holds across restarts."""
    with factory() as s:
        row = s.scalar(select(JobRun).where(JobRun.job_name == name, JobRun.scheduled_for == scheduled_for))
        if row is not None and row.status == "succeeded":
            raise JobAlreadyDone(f"{name} for {scheduled_for} already succeeded (job_run {row.id})")
        if row is None:
            row = JobRun(job_name=name, scheduled_for=scheduled_for, started_at=now, status="running")
            s.add(row)
            try:
                s.commit()
            except IntegrityError as e:
                s.rollback()
                raise JobAlreadyDone(f"{name} for {scheduled_for} claimed concurrently") from e
        else:
            row.started_at, row.status, row.error, row.finished_at = now, "running", None, None
            s.commit()
        return row.id


def finish_job(factory: sessionmaker[Session], job_id: int, now: datetime, status: str,
               stats: dict | None = None, error: str | None = None) -> None:  # fmt: skip
    with factory() as s:
        row = s.get(JobRun, job_id)
        row.finished_at, row.status, row.error = now, status, error
        row.stats_json = json.dumps(stats, sort_keys=True, default=str) if stats is not None else None
        s.commit()
