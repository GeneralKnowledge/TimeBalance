"""Data-quality checks. Each returns ``QualityIssue`` rows for ``data_quality_events``.

Checks report; they never repair. Nothing here forward-fills or drops a stored value.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from mpe.data.providers.base import ObservationRecord, QualityIssue


def _issue(name, severity, details, recs: Sequence[ObservationRecord]) -> QualityIssue:
    r = recs[0] if recs else None
    return QualityIssue(
        name, severity, details, symbol=r.symbol if r else None, source=r.source if r else None
    )


def check_timestamps(recs: Sequence[ObservationRecord]) -> list[QualityIssue]:
    out = []
    future = [r for r in recs if r.available_at > r.retrieved_at]
    if future:
        out.append(_issue("available_after_retrieval", "error",
                          {"count": len(future), "examples": [r.timestamp.isoformat() for r in future[:5]]},
                          recs))  # fmt: skip
    early = [r for r in recs if r.available_at < r.timestamp and r.interval != "snapshot"
             and r.source_ts is None]  # fmt: skip
    if early:
        out.append(_issue("available_before_bar_close", "error",
                          {"count": len(early), "examples": [r.timestamp.isoformat() for r in early[:5]]},
                          recs))  # fmt: skip
    return out


def check_ohlc(recs: Sequence[ObservationRecord]) -> list[QualityIssue]:
    bad, nonpos, negvol = [], [], []
    for r in recs:
        px = [v for v in (r.open, r.high, r.low, r.close) if v is not None]
        if any(v <= 0 for v in px):
            nonpos.append(r.timestamp.isoformat())
        if r.high is not None and r.low is not None:
            body = [v for v in (r.open, r.close) if v is not None]
            if r.low > r.high or any(v > r.high or v < r.low for v in body):
                bad.append(r.timestamp.isoformat())
        if r.volume is not None and r.volume < 0:
            negvol.append(r.timestamp.isoformat())
    out = []
    if bad:
        out.append(_issue("ohlc_inconsistent", "warning", {"count": len(bad), "examples": bad[:10]}, recs))
    if nonpos:
        out.append(
            _issue("non_positive_price", "error", {"count": len(nonpos), "examples": nonpos[:10]}, recs)
        )
    if negvol:
        out.append(_issue("negative_volume", "error", {"count": len(negvol), "examples": negvol[:10]}, recs))
    return out


def check_probability_bounds(recs: Sequence[ObservationRecord]) -> list[QualityIssue]:
    bad = [r.timestamp.isoformat() for r in recs
           for v in (r.close, r.bid, r.ask) if v is not None and not (Decimal(0) <= v <= Decimal(1))]  # fmt: skip
    return (
        [_issue("price_out_of_unit_interval", "error", {"count": len(bad), "examples": bad[:10]}, recs)]
        if bad
        else []
    )


def robust_z(x: np.ndarray) -> np.ndarray:
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med)) * 1.4826
    if not np.isfinite(mad) or mad == 0:
        return np.zeros_like(x)
    return (x - med) / mad


def check_outliers(
    recs: Sequence[ObservationRecord], z: float, use_logit: bool = False
) -> list[QualityIssue]:
    """Flag moves whose robust z-score (median/MAD) exceeds ``z``. Large moves happen (earnings,
    news, resolution), so this is a ``warning`` for a human, not a filter."""
    pts = [(r.timestamp, float(r.close)) for r in recs if r.close is not None]
    if len(pts) < 30:
        return []
    ts, px = zip(*pts, strict=True)
    p = np.asarray(px)
    if use_logit:
        p = np.clip(p, 1e-4, 1 - 1e-4)
        series = np.log(p / (1 - p))
    else:
        if (p <= 0).any():
            return []
        series = np.log(p)
    d = np.diff(series)
    zs = robust_z(d)
    idx = np.where(np.abs(zs) > z)[0]
    if not len(idx):
        return []
    ex = [{"timestamp": ts[i + 1].isoformat(), "move": round(float(d[i]), 6), "z": round(float(zs[i]), 1)}
          for i in idx[np.argsort(-np.abs(zs[idx]))][:10]]  # fmt: skip
    return [_issue("outlier_move", "warning", {"count": len(idx), "threshold_z": z, "largest": ex}, recs)]


def missing_sessions(timestamps: Sequence[datetime], calendar, start: datetime, end: datetime) -> list[str]:
    """Exchange sessions in [start, end] (by session date) that have no bar."""
    if start > end:
        return []
    sessions = calendar.sessions_in_range(pd.Timestamp(start.date()), pd.Timestamp(end.date()))
    closes = {calendar.session_close(s).to_pydatetime(): s for s in sessions}
    have = set(timestamps)
    return [s.strftime("%Y-%m-%d") for c, s in closes.items() if c not in have]


def check_missing_sessions(recs: Sequence[ObservationRecord], calendar, start: datetime | None = None,
                           end: datetime | None = None) -> list[QualityIssue]:  # fmt: skip
    if not recs:
        return []
    ts = [r.timestamp for r in recs]
    miss = missing_sessions(ts, calendar, start or min(ts), end or max(ts))
    if not miss:
        return []
    sev = "warning" if len(miss) <= 5 else "error"
    return [_issue("missing_sessions", sev, {"count": len(miss), "examples": miss[:20]}, recs)]


def check_gaps(
    recs: Sequence[ObservationRecord], step: timedelta, min_gap_steps: int = 6
) -> list[QualityIssue]:
    """For regular series (Polymarket hourly): report gaps of at least ``min_gap_steps`` steps."""
    ts = sorted(r.timestamp for r in recs)
    gaps = []
    for a, b in itertools.pairwise(ts):
        n = (b - a) / step
        if n >= min_gap_steps:
            gaps.append({"after": a.isoformat(), "missing_steps": math.floor(n) - 1})
    if not gaps:
        return []
    total = sum(g["missing_steps"] for g in gaps)
    return [_issue("history_gaps", "info", {"gaps": len(gaps), "missing_steps": total, "largest":
                   sorted(gaps, key=lambda g: -g["missing_steps"])[:5]}, recs)]  # fmt: skip


def sessions_since(calendar, last: datetime, now: datetime) -> int:
    """Completed sessions after ``last`` up to ``now`` (bars we should have but do not)."""
    if last >= now:
        return 0
    sessions = calendar.sessions_in_range(pd.Timestamp(last.date()), pd.Timestamp(now.date()))
    return sum(1 for s in sessions if last < calendar.session_close(s).to_pydatetime() <= now)


def stale_issue(symbol: str, source: str, last: datetime | None, now: datetime, behind: float,
                limit: float, unit: str) -> list[QualityIssue]:  # fmt: skip
    if last is None:
        return [QualityIssue("no_data", "error", {"now": now.isoformat()}, symbol=symbol, source=source)]
    if behind > limit:
        return [QualityIssue("stale_data", "warning", {"last": last.isoformat(), "behind": behind, "unit": unit,
                             "limit": limit}, symbol=symbol, source=source)]  # fmt: skip
    return []
