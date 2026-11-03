"""End-to-end ingestion against the offline fakes: idempotency, failures, corrections, CLI."""

import json

import httpx
import pytest
from sqlalchemy import func, select

from mpe.clock import FixedClock
from mpe.data.ingestion import Ingestor
from mpe.data.providers.polymarket import PolymarketProvider
from mpe.data.providers.yahoo import YahooProvider
from mpe.storage.orm import (
    Asset,
    DataQualityEvent,
    Market,
    Observation,
    OrderBookSnapshot,
    Resolution,
)
from tests.fakes import T0, FakePolymarket, db, gamma_market, settings, small_assets, yahoo_frame

DATA_TABLES = (Asset, Market, Observation, OrderBookSnapshot, Resolution, DataQualityEvent)


def counts(factory) -> dict:
    with factory() as s:
        return {t.__tablename__: s.scalar(select(func.count()).select_from(t)) for t in DATA_TABLES}


def dump(factory) -> list:
    with factory() as s:
        return [
            (o.asset_id, o.timestamp, o.source, o.version, o.close, o.volume)
            for o in s.scalars(select(Observation).order_by(Observation.id))
        ]


@pytest.fixture
def world(tmp_path):
    clock = FixedClock(T0)
    _, factory = db(tmp_path)
    s = settings()
    s.stocks.backfill_start = "2026-06-01"
    fake = FakePolymarket(
        [gamma_market(1, volume=9e6), gamma_market(2, volume=8e6), gamma_market(3, volume=7e6),
         gamma_market(4, neg_risk=True)],
        [gamma_market(10, closed=True, outcome_prices=["0", "1"]), gamma_market(11, closed=True, uma="disputed")],
        clock,
    )  # fmt: skip
    shift = {"v": 0.0}
    yahoo = YahooProvider(
        s, small_assets(), clock, downloader=lambda sym, a, b: yahoo_frame(sym, a, b, shift["v"])
    )
    pm = PolymarketProvider(s, clock, transport=fake.transport())
    ing = Ingestor(s, small_assets(), clock, factory, yahoo=yahoo, polymarket=pm)
    return ing, fake, factory, clock, shift


def test_backfill_stores_both_market_categories_with_provenance(world):
    ing, _fake, factory, clock, _ = world
    assert not ing.backfill_stocks().failed
    assert not ing.backfill_polymarket().failed
    with factory() as s:
        sel = s.scalars(select(Market).where(Market.selected == 1)).all()
        assert {m.question for m in sel} == {"Test market 1?", "Test market 2?", "Test market 10?"}
        assert {m.resolution_status for m in sel} == {"open", "resolved"}
        excluded = {
            m.question: m.selection_reason for m in s.scalars(select(Market).where(Market.selected == 0))
        }
        assert "multi-outcome" in excluded["Test market 4?"] and "disputed" in excluded["Test market 11?"]
        assert "outside top 2" in excluded["Test market 3?"]
        res = s.scalars(select(Resolution)).one()
        assert res.outcome == "NO"
        pm_assets = s.scalars(select(Asset).where(Asset.asset_type == "pm_token")).all()
        assert len(pm_assets) == 6 and {a.outcome_side for a in pm_assets} == {"YES", "NO"}
        closed_tokens = [a for a in pm_assets if a.market_id == res.market_id]
        assert all(a.active == 0 and a.delisted_at is not None for a in closed_tokens)
        obs = s.scalars(select(Observation)).all()
        assert {o.source for o in obs} == {"yfinance", "polymarket_clob_history", "polymarket_data_trades",
                                          "polymarket_clob_book"}  # fmt: skip
        assert all(o.retrieved_at == clock.now() and o.available_at <= o.retrieved_at for o in obs)
        assert s.scalar(select(func.count()).select_from(OrderBookSnapshot)) == 4  # 2 open markets x 2 tokens
        fx = s.scalars(select(Asset).where(Asset.symbol == "GBPUSD=X")).one()
        assert fx.asset_type == "fx"


def test_rerun_is_idempotent(world):
    ing, _fake, factory, _clock, _ = world
    ing.backfill_stocks()
    ing.backfill_polymarket()
    before, rows = counts(factory), dump(factory)
    for _ in range(2):
        ing.backfill_stocks()
        ing.update_stocks()
        rep = ing.sync_polymarket(full=False, books=False)
        assert not rep.failed
    after = counts(factory)
    assert dump(factory) == rows
    assert after["observations"] == before["observations"] and after["markets"] == before["markets"]


FAILURES = [
    lambda req: (_ for _ in ()).throw(httpx.ConnectTimeout("timed out", request=req)),
    lambda req: httpx.Response(429, headers={"Retry-After": "1"}),
    lambda req: httpx.Response(200, content=b'{"history": [{"t": 1, "p"'),
    lambda req: httpx.Response(200, json={"markets": "oops", "history": "oops", "data": "oops"}),
]
IDS = ["timeout", "429", "malformed-json", "wrong-shape"]


def markets_dump(factory):
    with factory() as s:
        return [
            (m.id, m.updated_at, m.selected, m.selection_reason, m.raw_json)
            for m in s.scalars(select(Market))
        ]


@pytest.mark.parametrize("failure", FAILURES, ids=IDS)
def test_polymarket_outage_leaves_db_unchanged(world, failure):
    ing, fake, factory, clock, _ = world
    ing.backfill_stocks()
    ing.backfill_polymarket()
    before, rows = counts(factory), dump(factory)
    clock.advance(hours=3)  # new data would be available...
    fake.price_shift = 0.05  # ...and old points would differ
    fake.fail["/"] = failure  # every route fails
    rep = ing.update_polymarket()
    assert rep.failed and all(not r.ok for r in rep.results if not r.stats.get("skipped"))
    assert counts(factory) == before and dump(factory) == rows


@pytest.mark.parametrize("failure", FAILURES, ids=IDS)
def test_failed_unit_writes_nothing_while_others_proceed(world, failure):
    ing, fake, factory, clock, _ = world
    ing.backfill_polymarket()
    clock.advance(hours=3)
    fake.price_shift = 0.05
    m_before, rows = markets_dump(factory), dump(factory)
    fake.fail["/markets/keyset"] = failure
    rep = ing.sync_polymarket(full=False, books=False, trades=False)
    assert [r.unit for r in rep.failed] == ["polymarket:markets"]
    assert markets_dump(factory) == m_before  # the failed unit changed nothing...
    assert len(dump(factory)) > len(rows)  # ...while history for the existing panel still updated

    del fake.fail["/markets/keyset"]
    fake.fail["/prices-history"] = failure
    rows = dump(factory)
    clock.advance(hours=3)
    rep = ing.sync_polymarket(full=False, books=False, trades=False)
    assert rep.results[0].ok
    assert all(not r.ok for r in rep.results[1:] if not r.stats.get("skipped")) and len(rep.failed) == 4
    assert dump(factory) == rows


def test_yahoo_failure_leaves_db_unchanged(world):
    ing, _fake, factory, _clock, _shift = world
    ing.backfill_stocks()
    before, rows = counts(factory), dump(factory)

    def boom(*a):
        raise RuntimeError("HTTP 429 Too Many Requests")

    ing.yahoo.download = boom
    rep = ing.update_stocks()
    assert len(rep.failed) == 3 and counts(factory) == before and dump(factory) == rows


def test_corrections_append_versions(world):
    ing, _fake, factory, clock, shift = world
    ing.backfill_stocks()
    with factory() as s:
        spy = s.scalars(select(Asset).where(Asset.symbol == "SPY")).one()
        old = {
            (o.timestamp, o.version): o.close
            for o in s.scalars(select(Observation).where(Observation.asset_id == spy.id))
        }
    shift["v"] = 0.25  # Yahoo revises the last bars
    clock.advance(days=1)
    rep = ing.update_stocks(["SPY"])
    assert rep.results[0].stats["corrected"] > 0
    with factory() as s:
        rows = s.scalars(select(Observation).where(Observation.asset_id == spy.id)).all()
        v1 = {(o.timestamp, o.version): o.close for o in rows if o.version == 1}
        assert {k: v1[k] for k in old} == old  # originals untouched (a new day also adds a bar)
        v2 = [o for o in rows if o.version == 2]
        assert v2 and all(o.retrieved_at == clock.now() for o in v2)


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    """`mpe ingest update` then `mpe data health` through the real CLI with the fakes patched in."""
    import mpe.data.providers.polymarket as pmmod
    import mpe.data.providers.yahoo as ymod
    from mpe.main import main

    clock = FixedClock(T0)
    fake = FakePolymarket([gamma_market(1)], [gamma_market(10, closed=True)], clock)
    monkeypatch.setenv("MPE_DATABASE", str(tmp_path / "cli.sqlite3"))
    real_init = pmmod.PolymarketProvider.__init__

    def init(self, settings_, clock_, budget=None, transport=None, on_raw=None):
        settings_.http.backoff_base_s = 0.01
        real_init(self, settings_, clock_, budget, transport=fake.transport(), on_raw=on_raw)

    monkeypatch.setattr(pmmod.PolymarketProvider, "__init__", init)
    monkeypatch.setattr(ymod, "yfinance_downloader", lambda s, a, b: yahoo_frame(s, a, b))
    monkeypatch.setattr(ymod.YahooProvider.__init__, "__defaults__", (ymod.yfinance_downloader, None))
    assert main(["ingest", "update", "--symbols", "SPY"], clock=clock) == 0
    assert main(["ingest", "update", "--symbols", "SPY"], clock=clock) == 0  # same slot: skipped
    out = capsys.readouterr().out
    assert "skip:" in out
    assert main(["data", "health", "--json"], clock=clock) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["markets"]["selected"] >= 1 and rep["jobs"][0]["status"] == "succeeded"
    spy = [a for a in rep["assets"] if a["symbol"] == "SPY"]
    assert spy and spy[0]["rows"] > 1000 and spy[0]["stale"] is False
    clock.advance(hours=1)
    assert main(["data", "health"], clock=clock) == 0
    assert "Data health" in capsys.readouterr().out
