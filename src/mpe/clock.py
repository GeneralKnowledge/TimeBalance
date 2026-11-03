"""Injectable clock. Nothing else in ``src/mpe`` reads the wall clock (enforced by a guard test).

Pass a :class:`Clock` into anything that needs "now"; tests use :class:`FixedClock`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...  # timezone-aware UTC

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class FixedClock:
    """Deterministic clock for tests. ``sleep`` advances time instead of blocking."""

    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._now = at.astimezone(UTC)
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self._now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += timedelta(seconds=seconds)

    def advance(self, **kw: float) -> None:
        self._now += timedelta(**kw)


def to_iso(dt: datetime) -> str:
    """Canonical UTC ISO-8601 text: ``2026-11-03T09:30:00Z`` (microseconds kept only if non-zero)."""
    if dt.tzinfo is None:
        raise ValueError(f"naive datetime {dt!r}; all timestamps must be timezone-aware UTC")
    dt = dt.astimezone(UTC)
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if dt.microsecond else "%Y-%m-%dT%H:%M:%SZ"
    return dt.strftime(fmt)


def from_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp {text!r} has no timezone")
    return dt.astimezone(UTC)


def from_epoch(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)
