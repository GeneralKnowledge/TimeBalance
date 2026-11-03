from datetime import UTC, datetime, timedelta

import exchange_calendars as xc
import numpy as np
import pytest

from mpe.data import validation as V
from mpe.data.normalisation import normalise
from mpe.data.providers.base import ObservationRecord
from mpe.storage.types import to_decimal

CAL = xc.get_calendar("XNYS", start="2020-01-01")


def bar(ts, close, **kw):
    return ObservationRecord(symbol="X", timestamp=ts, interval=kw.pop("interval", "1d"), source="s",
                             retrieved_at=kw.pop("retrieved", ts + timedelta(days=1)),
                             available_at=kw.pop("available", ts + timedelta(minutes=30)),
                             close=to_decimal(close), **{k: to_decimal(v) for k, v in kw.items()})  # fmt: skip


def closes(start, end):
    return [CAL.session_close(s).to_pydatetime() for s in CAL.sessions_in_range(start, end)]


def test_normalise_collapses_duplicates_and_rejects_naive_times():
    t = datetime(2026, 1, 5, 21, tzinfo=UTC)
    out, issues = normalise([bar(t, 1), bar(t + timedelta(days=1), 2), bar(t, 3)])
    assert [r.close for r in out] == [3, 2] and issues[0].check_name == "duplicate_timestamps"
    with pytest.raises(ValueError, match="naive"):
        normalise([bar(datetime(2026, 1, 5), 1, retrieved=datetime(2026, 1, 6, tzinfo=UTC),
                       available=datetime(2026, 1, 6, tzinfo=UTC))])  # fmt: skip


def test_missing_sessions_against_exchange_calendar():
    ts = closes("2026-03-02", "2026-03-31")
    recs = [bar(t, 100) for i, t in enumerate(ts) if i not in (3, 4)]
    (issue,) = V.check_missing_sessions(recs, CAL)
    assert issue.details["count"] == 2 and issue.details["examples"] == ["2026-03-05", "2026-03-06"]
    assert V.check_missing_sessions([bar(t, 100) for t in ts], CAL) == []  # holidays/weekends are not gaps


def test_outliers_ohlc_bounds_and_availability():
    ts = closes("2025-01-02", "2025-06-30")
    rng = np.random.default_rng(0)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(ts))))
    px[60] *= 1.5
    (o,) = V.check_outliers([bar(t, p) for t, p in zip(ts, px, strict=True)], z=8)
    flagged = {x["timestamp"][:10] for x in o.details["largest"]}
    assert ts[60].date().isoformat() in flagged  # the jump up (and the jump back down next day)
    t = ts[0]
    assert V.check_ohlc([bar(t, 10, high=9, low=8, open=8.5)])[0].check_name == "ohlc_inconsistent"
    assert V.check_ohlc([bar(t, -1)])[0].check_name == "non_positive_price"
    assert V.check_probability_bounds([bar(t, 1.2, interval="1h")])[0].severity == "error"
    assert V.check_timestamps([bar(t, 1, retrieved=t, available=t + timedelta(hours=1))])[0].check_name == (
        "available_after_retrieval"
    )


def test_gaps_and_staleness():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    hours = [t0 + timedelta(hours=h) for h in [*range(10), *range(30, 40)]]
    (g,) = V.check_gaps([bar(t, 0.5, interval="1h") for t in hours], timedelta(hours=1), min_gap_steps=6)
    assert g.details["missing_steps"] == 20
    last = CAL.session_close("2026-03-02").to_pydatetime()
    assert V.sessions_since(CAL, last, CAL.session_close("2026-03-05").to_pydatetime()) == 3
    assert (
        V.stale_issue("X", "s", last, last, behind=3, limit=2, unit="sessions")[0].check_name == "stale_data"
    )
