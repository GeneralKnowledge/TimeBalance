"""Two ways to read history at a simulated cutoff, kept deliberately separate.

``strict`` (:func:`mpe.storage.repositories.get_history`)
    What this system actually knew at ``as_of``: a row counts only if it was *retrieved* by
    ``as_of`` and its value was *available* by ``as_of``. Backfilled rows are invisible before
    their retrieval date. Use it to audit genuine historical behaviour (live forecasts, signals).

``reconstructed`` (:func:`get_reconstructed_history`)
    What the system *could* have known at ``as_of`` had it been running, rebuilt from data
    downloaded later. A row counts if its documented availability assumption (an
    :class:`AvailabilityRule`) says it was available by ``as_of``, whenever it was retrieved. It
    is for walk-forward research on backfills and is never contemporaneous knowledge: every row is
    labelled ``captured`` (retrieved by ``as_of``, so also strictly known) or ``reconstructed``.

Version rule for ``reconstructed``: if any version of a bar was retrieved by ``as_of`` the latest
such version is used (exactly what strict replay returns); otherwise the *earliest* captured
version is used, so a correction fetched later never reaches an earlier simulated cutoff.
Revisions the provider made before our first download are not recoverable: the earliest version
we hold may already include them (see docs/KNOWN_LIMITATIONS.md).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mpe.clock import to_iso
from mpe.data.providers.polymarket import SRC_BOOK, SRC_HISTORY, SRC_TRADES
from mpe.data.providers.yahoo import SOURCE as YAHOO_SOURCE
from mpe.storage.orm import Observation
from mpe.storage.repositories import SERIES

log = logging.getLogger(__name__)


class KnowledgeMode(StrEnum):
    STRICT = "strict_point_in_time"
    RECONSTRUCTED = "reconstructed_history"


class UnknownAvailabilityRule(ValueError):
    """No documented availability assumption exists for a (source, interval); refuse to guess."""


@dataclass(frozen=True)
class AvailabilityRule:
    """How a stored row's ``available_at`` is to be trusted when it was retrieved after the cutoff.

    ``event_end(row)`` is the earliest moment the value can exist (bar close, sample time). A row
    whose ``available_at`` is before it, or whose event time is missing, is invalid metadata and
    is excluded. ``reconstructable=False`` means the data cannot be rebuilt after the fact (live
    order-book snapshots): such rows are used only if retrieved by the cutoff.
    """

    description: str
    event_end: Callable[[Observation], datetime | None]
    reconstructable: bool = True


HOUR = timedelta(hours=1)

AVAILABILITY_RULES: dict[tuple[str, str], AvailabilityRule] = {
    (YAHOO_SOURCE, "1d"): AvailabilityRule(
        "daily bar: timestamp is the session close (XNYS calendar; 00:00 Europe/London for FX); "
        "available_at = close + availability.stock_close_delay_minutes / fx_close_delay_minutes",
        lambda o: o.timestamp,
    ),
    (SRC_HISTORY, "1h"): AvailabilityRule(
        "hourly price sample: filed under its hour, known at its own sample time source_ts; "
        "available_at = source_ts + availability.polymarket_history_latency_seconds",
        lambda o: o.source_ts,
    ),
    (SRC_TRADES, "1h"): AvailabilityRule(
        "hourly trade volume: complete only when the hour ends; available_at = hour end + latency",
        lambda o: o.timestamp + HOUR,
    ),
    (SRC_BOOK, "snapshot"): AvailabilityRule(
        "live order-book snapshot: cannot be rebuilt later; used only if retrieved by the cutoff",
        lambda o: o.retrieved_at,
        reconstructable=False,
    ),
}


def rule_for(source: str, interval: str) -> AvailabilityRule:
    try:
        return AVAILABILITY_RULES[(source, interval)]
    except KeyError:
        raise UnknownAvailabilityRule(
            f"no availability rule for source={source!r} interval={interval!r}; add one to "
            "mpe.storage.replay.AVAILABILITY_RULES before using it in reconstructed replay"
        ) from None


COLUMNS = ["timestamp", "source", "version", "available_at", "retrieved_at", "knowledge", *SERIES]


def get_reconstructed_history(
    session: Session,
    asset_id: int,
    as_of: datetime,
    interval: str,
    source: str | None = None,
    start: datetime | None = None,
    extra_latency: timedelta = timedelta(0),
) -> pd.DataFrame:
    """History as it could have been known at ``as_of`` under documented availability rules.

    Not contemporaneous knowledge: see the module docstring. ``extra_latency`` delays every
    row's availability further (a pessimistic ingestion delay). The frame carries provenance
    columns ``retrieved_at`` and ``knowledge`` and, in ``df.attrs["replay"]``, the mode, cutoff,
    rules and exclusion counts for an experiment's metadata. Stored rows are never modified.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware UTC")
    if extra_latency < timedelta(0):
        raise ValueError("extra_latency must not be negative")
    # SQL prefilter on stored availability (index-friendly); rules are applied per row below
    conds = [Observation.asset_id == asset_id, Observation.interval == interval,
             Observation.available_at <= to_iso(as_of - extra_latency)]  # fmt: skip
    if source is not None:
        conds.append(Observation.source == source)
    if start is not None:
        conds.append(Observation.timestamp >= to_iso(start))
    rows = session.scalars(select(Observation).where(*conds)).all()

    invalid = 0
    groups: dict[tuple[datetime, str], list[Observation]] = {}
    rules: dict[str, AvailabilityRule] = {}
    for o in rows:
        rule = rules.get(o.source) or rules.setdefault(o.source, rule_for(o.source, interval))
        captured = o.retrieved_at <= as_of
        if not rule.reconstructable and not captured:
            continue
        ev = rule.event_end(o)
        if ev is None or o.available_at < ev:
            invalid += 1
            continue
        groups.setdefault((o.timestamp, o.source), []).append(o)

    chosen: list[tuple[Observation, str]] = []
    for versions in groups.values():
        known = [o for o in versions if o.retrieved_at <= as_of]
        if known:
            chosen.append((max(known, key=lambda o: o.version), "captured"))
        else:
            chosen.append((min(versions, key=lambda o: o.version), "reconstructed"))
    chosen.sort(key=lambda t: (t[0].timestamp, t[0].source))

    if invalid:
        log.warning("reconstructed replay asset %s %s: %d rows excluded for invalid availability metadata",
                    asset_id, interval, invalid)  # fmt: skip
    data = [[o.timestamp, o.source, o.version, o.available_at, o.retrieved_at, k,
             *(getattr(o, c) for c in SERIES)] for o, k in chosen]  # fmt: skip
    df = pd.DataFrame(data, columns=COLUMNS)
    for c in ("timestamp", "available_at", "retrieved_at"):
        if not df.empty:
            df[c] = pd.to_datetime(df[c], utc=True)
    df.attrs["knowledge_mode"] = KnowledgeMode.RECONSTRUCTED.value
    df.attrs["replay"] = {
        "knowledge_mode": KnowledgeMode.RECONSTRUCTED.value,
        "as_of": to_iso(as_of),
        "interval": interval,
        "extra_latency_s": extra_latency.total_seconds(),
        "rules": {s: r.description for s, r in sorted(rules.items())},
        "rows_captured": sum(k == "captured" for _, k in chosen),
        "rows_reconstructed": sum(k == "reconstructed" for _, k in chosen),
        "excluded_invalid_availability": invalid,
    }
    return df
