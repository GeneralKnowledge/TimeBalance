import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from tests.fakes import db

from mpe.data.providers.base import Instrument, ObservationRecord
from mpe.storage import repositories as R
from mpe.storage.orm import Base, Observation
from mpe.storage.types import canonical, to_decimal

T = datetime(2026, 1, 5, 21, 0, tzinfo=UTC)


def rec(ts, close, retrieved, available=None, source="yfinance"):
    return ObservationRecord(symbol="SPY", timestamp=ts, interval="1d", source=source, retrieved_at=retrieved,
                             available_at=available or ts + timedelta(minutes=30), close=to_decimal(close))  # fmt: skip


def test_migration_creates_every_table_and_is_idempotent(tmp_path):
    engine, _ = db(tmp_path)
    from mpe.storage.database import upgrade

    upgrade(engine)  # second run is a no-op
    names = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= names


def test_decimal_columns_have_text_affinity_and_round_trip(tmp_path):
    engine, factory = db(tmp_path)
    with factory() as s:
        a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
        R.write_observations(s, a.id, [rec(T, "0.1", T + timedelta(hours=1))])
        s.commit()
        o = s.query(Observation).one()
        assert o.close == Decimal("0.1") and isinstance(o.close, Decimal)
    with engine.connect() as c:
        assert c.execute(text("select typeof(close), close from observations")).one() == ("text", "0.1")


@pytest.mark.parametrize(("v", "out"), [(0.1, "0.1"), ("1.50", "1.5"), (Decimal("1E+2"), "100"), (0, "0")])
def test_canonical_decimal_text(v, out):
    assert canonical(to_decimal(v)) == out


def test_to_decimal_rejects_non_finite_and_naive_timestamps():
    import numpy as np

    assert to_decimal(float("nan")) is None and to_decimal(np.float64(2.5)) == Decimal("2.5")
    with pytest.raises(ValueError):
        R.get_history(None, 1, datetime(2026, 1, 1), "1d")


def test_immutable_tables_reject_update_and_delete(tmp_path):
    _engine, _ = db(tmp_path)
    con = sqlite3.connect(tmp_path / "t.sqlite3")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute(
        "insert into assets(id,symbol,asset_type,currency,provider,active) values (1,'X','etf','USD','p',1)"
    )
    con.execute("insert into model_runs(id,model_name,model_version,code_version,configuration,mode,started_at,status)"
                " values (1,'m','v','c','{}','backtest','2026-01-01T00:00:00Z','succeeded')")  # fmt: skip
    con.execute("insert into forecasts(model_run_id,asset_id,forecast_type,created_at,input_cutoff_timestamp,"
                "target_timestamp,horizon,horizon_unit,forecast_values,quantiles,context_length,"
                "context_start_timestamp,input_hash) values (1,1,'log_return','t','t','t',1,'trading_day','{}','{}',1,'t','h')")  # fmt: skip
    con.commit()
    for stmt in ("update forecasts set horizon=2", "delete from forecasts"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute(stmt)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("insert into orders(asset_id,side,order_type,quantity,idempotency_key,is_paper,created_at)"
                    " values (1,'buy','market','1','k',0,'t')")  # fmt: skip


def test_rewrite_is_idempotent_and_correction_appends_version(tmp_path):
    _, factory = db(tmp_path)
    t1 = T + timedelta(hours=2)
    with factory() as s:
        a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
        assert (
            R.write_observations(s, a.id, [rec(T, "100", t1), rec(T + timedelta(days=1), "101", t1)]).inserted
            == 2
        )
        st = R.write_observations(s, a.id, [rec(T, "100.00", t1 + timedelta(days=1))])
        assert (st.inserted, st.unchanged, st.corrected) == (0, 1, 0)
        st = R.write_observations(s, a.id, [rec(T, "99.5", t1 + timedelta(days=2))])
        assert st.corrected == 1
        s.commit()
        rows = s.query(Observation).filter(Observation.timestamp == T).order_by(Observation.version).all()
        assert [(o.version, o.close) for o in rows] == [(1, Decimal(100)), (2, Decimal("99.5"))]
        assert rows[0].retrieved_at == t1  # the original row is untouched
        with pytest.raises(IntegrityError):  # the unique key forbids a second copy of a version
            s.add(Observation(asset_id=a.id, timestamp=T, interval="1d", source="yfinance", version=1,
                              retrieved_at=t1, available_at=t1))  # fmt: skip
            s.flush()


def test_point_in_time_accessor_hides_future_data_and_later_corrections(tmp_path):
    _, factory = db(tmp_path)
    fetched = T + timedelta(hours=1)
    with factory() as s:
        a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
        R.write_observations(s, a.id, [rec(T, "100", fetched)])
        # planted future bar: its close is not known until the day after
        R.write_observations(s, a.id, [rec(T + timedelta(days=1), "999", T + timedelta(days=1, hours=1))])
        # a correction to the first bar, fetched three days later
        R.write_observations(s, a.id, [rec(T, "100.7", T + timedelta(days=3))])
        s.commit()
        h = R.get_history(s, a.id, as_of=T + timedelta(hours=2), interval="1d")
        assert list(h["close"]) == [Decimal(100)]
        assert R.get_history(
            s, a.id, as_of=T + timedelta(minutes=10), interval="1d"
        ).empty  # before available_at
        h = R.get_history(s, a.id, as_of=T + timedelta(days=4), interval="1d")
        assert list(h["close"]) == [Decimal("100.7"), Decimal(999)]
        assert list(h["version"]) == [2, 1]


def test_job_claim_prevents_duplicate_runs(tmp_path):
    _, factory = db(tmp_path)
    jid = R.start_job(factory, "ingest_update", "2026-01-01T10:00Z", T)
    R.finish_job(factory, jid, T, "failed", error="boom")
    jid2 = R.start_job(factory, "ingest_update", "2026-01-01T10:00Z", T)  # failed: retried in place
    assert jid2 == jid
    R.finish_job(factory, jid, T, "succeeded", {"ok": 1})
    with pytest.raises(R.JobAlreadyDone):
        R.start_job(factory, "ingest_update", "2026-01-01T10:00Z", T)


def test_request_budget_persists_and_stops(tmp_path):
    from mpe.clock import FixedClock
    from mpe.data.providers.base import BudgetExhausted

    _, factory = db(tmp_path)
    clock = FixedClock(T)
    b = R.DbRequestBudget(factory, clock, {"polymarket": 5}, flush_every=2)
    for _ in range(3):
        b.consume("polymarket")
    b.flush()
    b2 = R.DbRequestBudget(factory, clock, {"polymarket": 5})  # e.g. after a restart
    assert b2.used("polymarket") == 3
    b2.consume("polymarket", 2)
    with pytest.raises(BudgetExhausted):
        b2.consume("polymarket")
    clock.advance(days=1)
    b2.consume("polymarket")  # a new UTC day has a fresh budget


def test_yahoo_adj_close_wobble_is_not_a_correction(tmp_path):
    _, factory = db(tmp_path)
    t1 = T + timedelta(hours=2)

    def r(adj):
        return ObservationRecord(symbol="SPY", timestamp=T, interval="1d", source="yfinance", retrieved_at=t1,
                                 available_at=T, close=to_decimal("113.63"), adj_close=to_decimal(adj))  # fmt: skip

    with factory() as s:
        a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
        R.write_observations(s, a.id, [r("84.5923")])
        assert R.write_observations(s, a.id, [r("84.59229")]).unchanged == 1  # last-digit noise
        assert R.write_observations(s, a.id, [r("84.41")]).corrected == 1  # a real re-adjustment
