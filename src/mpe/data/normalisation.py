"""Shared normalisation applied to every provider's records before validation and storage."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC

from mpe.data.providers.base import ObservationRecord, QualityIssue


def normalise(records: Sequence[ObservationRecord]) -> tuple[list[ObservationRecord], list[QualityIssue]]:
    """UTC-normalise, sort by time, and collapse duplicate timestamps (last one wins, reported).

    Never fills gaps or invents values: what comes out is a subset of what went in.
    """
    issues: list[QualityIssue] = []
    out: dict[tuple, ObservationRecord] = {}
    dupes: list[str] = []
    for r in records:
        for name in ("timestamp", "retrieved_at", "available_at", "source_ts"):
            v = getattr(r, name)
            if v is not None and v.tzinfo is None:
                raise ValueError(f"{r.symbol}: naive {name} {v!r}; providers must emit UTC")
        r = replace(
            r,
            timestamp=r.timestamp.astimezone(UTC),
            retrieved_at=r.retrieved_at.astimezone(UTC),
            available_at=r.available_at.astimezone(UTC),
            source_ts=r.source_ts.astimezone(UTC) if r.source_ts else None,
        )
        key = (r.symbol, r.interval, r.source, r.timestamp)
        if key in out:
            dupes.append(r.timestamp.isoformat())
        out[key] = r
    if dupes:
        issues.append(QualityIssue("duplicate_timestamps", "warning",
                                   {"count": len(dupes), "examples": dupes[:10]},
                                   symbol=records[0].symbol, source=records[0].source))  # fmt: skip
    return sorted(out.values(), key=lambda r: (r.symbol, r.interval, r.source, r.timestamp)), issues
