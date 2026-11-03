"""Strict point-in-time replay vs reconstructed historical replay (mpe.storage.replay)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tests.fakes import db

from mpe.data.providers.base import Instrument, ObservationRecord
from mpe.data.providers.polymarket import SRC_BOOK, SRC_HISTORY, SRC_TRADES
from mpe.storage import repositories as R
from mpe.storage.orm import Observation
from mpe.storage.replay import (
    AVAILABILITY_RULES,
    KnowledgeMode,
    UnknownAvailabilityRule,
    get_reconstructed_history,
)
from mpe.storage.types import to_decimal

CLOSE = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)  # SPY session close, 2024-01-02
AVAIL = CLOSE + timedelta(minutes=30)
BACKFILLED = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)  # downloaded years later
DAY = timedelta(days=1)


def bar(ts, close, retrieved, available=None, source="yfinance", interval="1d", **kw):
    return ObservationRecord(symbol="X", timestamp=ts, interval=interval, source=source, retrieved_at=retrieved,
                             available_at=available or ts + timedelta(minutes=30),
                             close=to_decimal(close) if close is not None else None, **kw)  # fmt: skip


@pytest.fixture
def spy(tmp_path):
    _, factory = db(tmp_path)
    s = factory()
    a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
    yield s, a.id
    s.close()


def write(s, aid, *recs):
    for r in recs:
        R.write_observations(s, aid, [r])
    s.commit()


def test_backfilled_bar_excluded_from_strict_but_included_in_reconstructed(spy):
    s, aid = spy
    write(s, aid, bar(CLOSE, "472.65", BACKFILLED, adj_close=to_decimal("458.1")))
    as_of = CLOSE + DAY
    assert R.get_history(s, aid, as_of, "1d").empty  # strict: we did not have it in 2024
    h = get_reconstructed_history(s, aid, as_of, "1d")
    assert list(h["close"]) == [Decimal("472.65")]
    # provenance and original timestamps are preserved, and the row is labelled reconstructed
    assert h["timestamp"].iloc[0] == CLOSE and h["available_at"].iloc[0] == AVAIL
    assert h["retrieved_at"].iloc[0] == BACKFILLED
    assert list(h["knowledge"]) == ["reconstructed"] and h["source"].iloc[0] == "yfinance"
    o = s.query(Observation).one()
    assert (o.timestamp, o.available_at, o.retrieved_at, o.version) == (CLOSE, AVAIL, BACKFILLED, 1)


def test_reconstructed_excludes_bar_not_yet_available_at_cutoff(spy):
    s, aid = spy
    write(s, aid, bar(CLOSE, "472.65", BACKFILLED))
    assert get_reconstructed_history(s, aid, CLOSE - timedelta(hours=5), "1d").empty  # mid-session
    assert get_reconstructed_history(s, aid, CLOSE + timedelta(minutes=10), "1d").empty  # before +30 min
    assert len(get_reconstructed_history(s, aid, AVAIL, "1d")) == 1  # inclusive at available_at
    # a configurable extra ingestion latency pushes availability later
    lat = timedelta(minutes=45)
    assert get_reconstructed_history(s, aid, AVAIL + timedelta(minutes=30), "1d", extra_latency=lat).empty
    h = get_reconstructed_history(s, aid, AVAIL + lat, "1d", extra_latency=lat)
    assert len(h) == 1 and h.attrs["replay"]["extra_latency_s"] == 2700
    with pytest.raises(ValueError):
        get_reconstructed_history(s, aid, AVAIL, "1d", extra_latency=-lat)


def test_later_versions_do_not_leak_into_earlier_simulated_cutoffs(spy):
    s, aid = spy
    # backfilled bar, then a correction fetched a month later: reconstructed replay of 2024 must
    # use the first captured version, never the later revision
    write(s, aid, bar(CLOSE, "100", BACKFILLED), bar(CLOSE, "99", BACKFILLED + 28 * DAY))
    h = get_reconstructed_history(s, aid, CLOSE + DAY, "1d")
    assert list(h["close"]) == [Decimal(100)] and list(h["version"]) == [1]
    # once the cutoff passes the correction's retrieval, it is genuinely known: strict and
    # reconstructed agree and the row is labelled captured
    late = BACKFILLED + 30 * DAY
    h = get_reconstructed_history(s, aid, late, "1d")
    assert list(h["close"]) == [Decimal(99)] and list(h["knowledge"]) == ["captured"]
    assert list(R.get_history(s, aid, late, "1d")["close"]) == [Decimal(99)]


def test_live_captured_corrections_follow_strict_semantics(spy):
    s, aid = spy
    fetched = CLOSE + timedelta(hours=1)
    write(s, aid, bar(CLOSE, "100", fetched), bar(CLOSE, "100.7", CLOSE + 3 * DAY),
          bar(CLOSE + DAY, "101", CLOSE + DAY + timedelta(hours=1)))  # fmt: skip
    for as_of in (CLOSE + timedelta(hours=2), CLOSE + 2 * DAY, CLOSE + 4 * DAY):
        strict = R.get_history(s, aid, as_of, "1d")
        recon = get_reconstructed_history(s, aid, as_of, "1d")
        assert list(recon["close"]) == list(strict["close"])
        assert list(recon["version"]) == list(strict["version"])
        assert set(recon["knowledge"]) == {"captured"}


def test_strict_get_history_contract_is_unchanged(spy):
    s, aid = spy
    write(s, aid, bar(CLOSE, "100", CLOSE + timedelta(hours=1)))
    h = R.get_history(s, aid, CLOSE + DAY, "1d")
    assert list(h.columns) == ["timestamp", "source", "version", "available_at", *R.SERIES]
    assert h.attrs["knowledge_mode"] == KnowledgeMode.STRICT == "strict_point_in_time"
    r = get_reconstructed_history(s, aid, CLOSE + DAY, "1d")
    assert r.attrs["knowledge_mode"] == KnowledgeMode.RECONSTRUCTED != h.attrs["knowledge_mode"]
    meta = r.attrs["replay"]
    assert meta["knowledge_mode"] == "reconstructed_history" and meta["as_of"] == "2024-01-03T21:00:00Z"
    assert "yfinance" in meta["rules"] and meta["rows_captured"] == 1
    with pytest.raises(ValueError):
        get_reconstructed_history(s, aid, datetime(2024, 1, 3), "1d")  # naive cutoff


def test_invalid_availability_metadata_is_excluded_and_counted(spy):
    s, aid = spy
    # available_at before the bar's own close cannot be true: never trusted
    write(s, aid, bar(CLOSE, "100", BACKFILLED, available=CLOSE - timedelta(hours=2)),
          bar(CLOSE + DAY, "101", BACKFILLED))  # fmt: skip
    h = get_reconstructed_history(s, aid, CLOSE + 3 * DAY, "1d")
    assert list(h["close"]) == [Decimal(101)]
    assert h.attrs["replay"]["excluded_invalid_availability"] == 1


def test_unknown_source_has_no_availability_rule(spy):
    s, aid = spy
    write(s, aid, bar(CLOSE, "100", BACKFILLED, source="mystery_vendor"))
    with pytest.raises(UnknownAvailabilityRule, match="mystery_vendor"):
        get_reconstructed_history(s, aid, CLOSE + DAY, "1d")
    assert len(R.get_history(s, aid, BACKFILLED, "1d")) == 1  # strict replay needs no rule


def test_every_ingested_source_has_a_rule():
    assert {("yfinance", "1d"), (SRC_HISTORY, "1h"), (SRC_TRADES, "1h"), (SRC_BOOK, "snapshot")} == set(
        AVAILABILITY_RULES
    )


@pytest.fixture
def token(tmp_path):
    _, factory = db(tmp_path)
    s = factory()
    a = R.get_or_create_asset(s, Instrument("tok1", "polymarket", "pm_token", outcome_side="YES"))
    yield s, a.id
    s.close()


def test_polymarket_history_sample_is_known_at_its_sample_time_not_its_hour(token):
    s, aid = token
    hour = datetime(2024, 10, 1, 10, 0, tzinfo=UTC)
    sample = hour + timedelta(minutes=50)
    write(s, aid, bar(hour, "0.55", BACKFILLED, available=sample + timedelta(seconds=60),
                      source=SRC_HISTORY, interval="1h", source_ts=sample))  # fmt: skip
    # the row is filed under 10:00 but its value is from 10:50: not usable at 10:30
    assert get_reconstructed_history(s, aid, hour + timedelta(minutes=30), "1h").empty
    assert len(get_reconstructed_history(s, aid, sample + timedelta(minutes=2), "1h")) == 1
    assert R.get_history(s, aid, sample + timedelta(minutes=2), "1h").empty  # strict: not fetched yet


def test_polymarket_history_without_sample_time_is_invalid(token):
    s, aid = token
    hour = datetime(2024, 10, 1, 10, 0, tzinfo=UTC)
    write(s, aid, bar(hour, "0.55", BACKFILLED, available=hour + timedelta(minutes=1),
                      source=SRC_HISTORY, interval="1h"))  # fmt: skip
    h = get_reconstructed_history(s, aid, hour + DAY, "1h")
    assert h.empty and h.attrs["replay"]["excluded_invalid_availability"] == 1


def test_polymarket_trade_volume_known_only_after_the_hour(token):
    s, aid = token
    hour = datetime(2024, 10, 1, 10, 0, tzinfo=UTC)
    write(s, aid, ObservationRecord(symbol="tok1", timestamp=hour, interval="1h", source=SRC_TRADES,
                                    retrieved_at=BACKFILLED, available_at=hour + timedelta(hours=1, seconds=60),
                                    volume=Decimal(1234), trade_count=7))  # fmt: skip
    assert get_reconstructed_history(s, aid, hour + timedelta(minutes=59), "1h").empty
    assert list(get_reconstructed_history(s, aid, hour + timedelta(minutes=62), "1h")["volume"]) == [1234]
    # a trade row claiming availability inside its own hour is invalid
    write(s, aid, ObservationRecord(symbol="tok1", timestamp=hour + DAY, interval="1h", source=SRC_TRADES,
                                    retrieved_at=BACKFILLED, available_at=hour + DAY + timedelta(minutes=5),
                                    volume=Decimal(1)))  # fmt: skip
    h = get_reconstructed_history(s, aid, hour + 2 * DAY, "1h")
    assert len(h) == 1 and h.attrs["replay"]["excluded_invalid_availability"] == 1


def test_order_book_snapshots_are_never_reconstructed(token):
    s, aid = token
    t = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    write(s, aid, ObservationRecord(symbol="tok1", timestamp=t, interval="snapshot", source=SRC_BOOK,
                                    retrieved_at=t, available_at=t, source_ts=t, close=Decimal("0.5"),
                                    bid=Decimal("0.49"), ask=Decimal("0.51")))  # fmt: skip
    assert get_reconstructed_history(s, aid, t - timedelta(minutes=1), "snapshot").empty
    h = get_reconstructed_history(s, aid, t, "snapshot")
    assert list(h["knowledge"]) == ["captured"] and list(h["bid"]) == [Decimal("0.49")]
