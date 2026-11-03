"""Resolved-market sample and decision points for the decision-model experiment.

Fetches resolved binary Polymarket markets through the existing :class:`PolymarketProvider`
(Gamma discovery + CLOB hourly ``prices-history``) into the decision store, then creates
snapshots at fixed lead times before each market's *scheduled* end.

Everything here is **reconstructed**: the history was retrieved after resolution, and
``available_at`` is the provider's backfill rule (point time + latency), not a recorded arrival.
The sample is selected by lifetime volume, which is known only afterwards; that selection is a
documented bias of the sample, never a model input.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from mpe.data.providers.base import Instrument, ProviderError
from mpe.data.providers.polymarket import PolymarketProvider, parse_market
from mpe.decisions.snapshot import PricePoint, build_snapshot, iso, parse_iso, snapshot_id
from mpe.decisions.store import DecisionStore

log = logging.getLogger(__name__)

DEFAULT_LEADS_H = (168, 48, 24, 6)
HISTORY_BEFORE_DAYS = 10  # history fetched before the earliest decision point
MIN_POINTS_AT_DECISION = 24


def fetch_resolved_markets(
    provider: PolymarketProvider, store: DecisionStore, *, end_min: datetime, end_max: datetime,
    max_markets: int, min_volume: float, include_neg_risk: bool, leads_h=DEFAULT_LEADS_H,
) -> dict:  # fmt: skip
    """Add up to ``max_markets`` resolved YES/NO markets that ended in [end_min, end_max)."""
    stats = {"seen": 0, "added": 0, "skipped": {}}

    def skip(reason: str) -> None:
        stats["skipped"][reason] = stats["skipped"].get(reason, 0) + 1

    pages = provider.iter_markets(closed=True, max_markets=max_markets * 20,
                                  end_date_min=iso(end_min), end_date_max=iso(end_max))  # fmt: skip
    for raw in pages:
        if stats["added"] >= max_markets:
            break
        stats["seen"] += 1
        m = parse_market(raw)
        if not m.is_binary or not m.yes_token_id:
            skip("not_binary")
            continue
        if m.neg_risk and not include_neg_risk:
            skip("neg_risk")
            continue
        if m.resolution_status != "resolved" or m.resolution_value not in ("YES", "NO"):
            skip("not_resolved_yes_no")
            continue
        if m.volume < min_volume:
            skip("low_volume")
            continue
        if m.closing_time is None:
            skip("no_scheduled_end")
            continue
        if store.has_market(m.condition_id):
            skip("already_stored")
            continue
        end = m.closing_time
        start = end - timedelta(hours=max(leads_h)) - timedelta(days=HISTORY_BEFORE_DAYS)
        try:
            recs = provider.fetch_history(
                Instrument(symbol=m.yes_token_id, provider="polymarket", asset_type="pm_token",
                           outcome_side="YES", market_key=m.condition_id),
                start, end + timedelta(days=2),
            )  # fmt: skip
        except ProviderError as e:
            log.warning("history failed for %s: %s", m.condition_id, e)
            skip("history_error")
            continue
        if len(recs) < MIN_POINTS_AT_DECISION:
            skip("short_history")
            continue
        now = provider.clock.now()
        row = {
            "condition_id": m.condition_id, "question": m.question, "description": m.description,
            "category": m.category,
            "opening_time": iso(m.opening_time) if m.opening_time else None,
            "scheduled_end": iso(end), "closed_time": iso(m.closed_time) if m.closed_time else None,
            "resolved_at": iso(m.closed_time or end), "outcome": m.resolution_value,
            "yes_token_id": m.yes_token_id, "fee_rate": None if m.fee_rate is None else float(m.fee_rate),
            "neg_risk": int(m.neg_risk), "final_volume": m.volume, "retrieved_at": iso(now),
            "raw_json": json.dumps(m.raw),
        }  # fmt: skip
        hist = [
            {"condition_id": m.condition_id, "ts": iso(r.timestamp), "price": float(r.close),
             "source_ts": iso(r.source_ts) if r.source_ts else None, "available_at": iso(r.available_at),
             "retrieved_at": iso(r.retrieved_at)}
            for r in recs if r.close is not None and not r.quality_flags
        ]  # fmt: skip
        store.insert_market(row, hist)
        stats["added"] += 1
    return stats


def history_points(store: DecisionStore, cid: str) -> list[PricePoint]:
    return [
        PricePoint(parse_iso(h["ts"]), h["price"], parse_iso(h["available_at"])) for h in store.history(cid)
    ]


def make_snapshots(store: DecisionStore, leads_h=DEFAULT_LEADS_H) -> dict:
    """Create a snapshot at each lead before the scheduled end, while the market was still open."""
    stats = {"created": 0, "skipped": {}}

    def skip(reason: str) -> None:
        stats["skipped"][reason] = stats["skipped"].get(reason, 0) + 1

    rows = []
    for m in store.markets():
        hist = history_points(store, m["condition_id"])
        end = parse_iso(m["scheduled_end"])
        closed = parse_iso(m["closed_time"]) if m["closed_time"] else end
        for lead in leads_h:
            t = end - timedelta(hours=lead)
            if t >= closed - timedelta(hours=1):
                skip("market_closed_before_decision")
                continue
            if sum(1 for p in hist if p.available_at <= t) < MIN_POINTS_AT_DECISION:
                skip("short_history_at_decision")
                continue
            static = {k: m[k] for k in ("condition_id", "question", "description", "category",
                                        "scheduled_end", "opening_time")}  # fmt: skip
            snap = build_snapshot(static, hist, t)
            rows.append({"snapshot_id": snapshot_id(snap), "condition_id": m["condition_id"],
                         "decision_ts": snap["decision_ts"], "lead_hours": lead, "schema": snap["schema"],
                         "reconstructed": 1, "snapshot_json": json.dumps(snap, sort_keys=True)})  # fmt: skip
    store.insert_snapshots(rows)
    stats["created"] = len(rows)
    return stats
