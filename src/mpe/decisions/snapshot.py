"""Point-in-time Polymarket snapshots for decision models.

A snapshot is built from a market's static metadata and its YES-price history, using only
observations with ``available_at <= decision_ts``. Fields we cannot know at the decision time
(lifetime volume and liquidity as reported by Gamma *after* resolution, the historical order book,
news) are listed under ``unavailable`` instead of being filled in. Outcomes and future prices
never enter a snapshot; :mod:`mpe.decisions.evaluate` reads them separately.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

SNAPSHOT_SCHEMA = "polymarket-snapshot/v1"
STATE_TEMPLATE = "laya-state/v1"
MAX_DESCRIPTION_CHARS = 1200
RECENT_POINTS = 24

UNAVAILABLE = {
    "volume": "only lifetime volume after resolution is stored; not known at the decision time",
    "liquidity": "only post-resolution liquidity is stored; not known at the decision time",
    "spread": "historical order books are not available; the simulation assumes a configured spread",
    "news": "no timestamped news source is ingested",
}


class LeakageError(ValueError):
    """An observation dated after the decision timestamp reached a snapshot."""


@dataclass(frozen=True)
class PricePoint:
    ts: datetime  # hour bucket (UTC)
    price: float  # YES price 0..1
    available_at: datetime


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


def known_at(history: list[PricePoint], decision_ts: datetime) -> list[PricePoint]:
    return [p for p in history if p.available_at <= decision_ts]


def price_at_or_before(history: list[PricePoint], t: datetime) -> float | None:
    """Last price whose hour bucket is <= t (history sorted by ts)."""
    best = None
    for p in history:
        if p.ts <= t:
            best = p.price
        else:
            break
    return best


def build_snapshot(market: dict, history: list[PricePoint], decision_ts: datetime) -> dict:
    """Snapshot dict for one market at ``decision_ts``. ``market`` holds static metadata only."""
    hist = sorted(known_at(history, decision_ts), key=lambda p: p.ts)
    if any(p.available_at > decision_ts for p in hist):
        raise LeakageError("future observation in snapshot")
    if not hist:
        raise ValueError("no price known at the decision time")
    last = hist[-1]
    price = last.price

    def change(hours: int) -> float | None:
        prev = price_at_or_before(hist, last.ts - timedelta(hours=hours))
        return None if prev is None else round(price - prev, 4)

    window = [p.price for p in hist if p.ts > last.ts - timedelta(days=7)]
    steps = [b.price - a.price for a, b in zip(hist[-25:], hist[-24:], strict=False)]
    vol = math.sqrt(sum(s * s for s in steps) / len(steps)) if steps else None
    end = parse_iso(market["scheduled_end"]) if market.get("scheduled_end") else None
    opened = parse_iso(market["opening_time"]) if market.get("opening_time") else None
    desc = (market.get("description") or "").strip()
    return {
        "schema": SNAPSHOT_SCHEMA,
        "decision_ts": iso(decision_ts),
        "reconstructed": True,
        "market": {
            "condition_id": market["condition_id"],
            "question": market["question"],
            "description": desc[:MAX_DESCRIPTION_CHARS] + ("…" if len(desc) > MAX_DESCRIPTION_CHARS else ""),
            "category": market.get("category"),
            "scheduled_end": market.get("scheduled_end"),
            "hours_to_scheduled_end": None
            if end is None
            else round((end - decision_ts).total_seconds() / 3600, 1),
            "market_age_days": None
            if opened is None
            else round((decision_ts - opened).total_seconds() / 86400, 1),
        },
        "price": {
            "yes": round(price, 4),
            "no_implied": round(1 - price, 4),
            "last_observation": iso(last.ts),
            "change_1h": change(1),
            "change_6h": change(6),
            "change_24h": change(24),
            "change_7d": change(168),
            "high_7d": round(max(window), 4),
            "low_7d": round(min(window), 4),
            "hourly_volatility_24h": None if vol is None else round(vol, 4),
            "observations": len(hist),
        },
        "recent_hourly_yes": [round(p.price, 3) for p in hist[-RECENT_POINTS:]],
        "unavailable": UNAVAILABLE,
    }


def _pct(x: float | None) -> str:
    return "unknown" if x is None else f"{x * 100:+.1f} points"


def render_state(snapshot: dict) -> dict:
    """The text the decision model reads (versioned by STATE_TEMPLATE). Numbers are spelled out
    in percentage points because Laya reads text, not arrays."""
    m, p = snapshot["market"], snapshot["price"]
    hours = m["hours_to_scheduled_end"]
    return {
        "market question": m["question"],
        "resolution rules": m["description"] or "not given",
        "category": m["category"] or "unknown",
        "time remaining": "unknown" if hours is None else f"{hours:.0f} hours until scheduled end",
        "current YES price": f"{p['yes'] * 100:.1f}% (market-implied probability of YES)",
        "price change": (
            f"1h {_pct(p['change_1h'])}, 6h {_pct(p['change_6h'])}, 24h {_pct(p['change_24h'])}, "
            f"7d {_pct(p['change_7d'])}"
        ),
        "7-day range": f"{p['low_7d'] * 100:.1f}% to {p['high_7d'] * 100:.1f}%",
        "hourly volatility (24h)": (
            "unknown"
            if p["hourly_volatility_24h"] is None
            else f"{p['hourly_volatility_24h'] * 100:.2f} points"
        ),
        "recent hourly YES prices (oldest first)": ", ".join(
            f"{v * 100:.1f}" for v in snapshot["recent_hourly_yes"]
        ),
        "not available": "volume, liquidity, order book spread and news at this time",
    }


def snapshot_id(snapshot: dict) -> str:
    blob = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
