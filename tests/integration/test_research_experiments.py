"""M2 research laboratory end to end on small offline fixtures (no network, weights, GPU or real DB)."""

from __future__ import annotations

import ast
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mpe.research import analysis as A
from mpe.research import data as D
from mpe.research.config import BASELINE_MODELS, ExperimentConfig, default_config, model_spec
from mpe.research.report import write_report
from mpe.research.runner import DataChanged, ExperimentRunner, VersionChanged
from mpe.research.store import ExperimentExists, ResearchStore, make_research_engine
from mpe.storage.replay import KnowledgeMode
from tests.research_fakes import (
    BACKFILLED,
    NOW,
    FakeTimestral,
    MarketDB,
    clock,
    fake_factory,
    random_walk,
    research_store,
    sessions,
    settings,
    stock_records,
    utc,
)

ROOT = Path(__file__).resolve().parents[2]
FAST = {"n_origins": 30, "max_context": 4096}
MODELS = ["timestral-5m", "timestral-209m", *BASELINE_MODELS]


def fast_models(names=MODELS):
    out = []
    for n in names:
        out.append(model_spec(n, **FAST) if n in BASELINE_MODELS else model_spec(n))
    return out


def stock_cfg(**kw) -> ExperimentConfig:
    base = dict(  # noqa: C408
        name="t", knowledge_mode="reconstructed_history", assets=["SPY", "QQQ"], settings=settings(),
        origin_start=utc(2023, 6, 1), origin_end=utc(2023, 9, 30), targets_as_of=utc(2023, 12, 1),
        context_length=60, min_context_observations=55, origin_stride=5, models=fast_models(),
        bootstrap_samples=200, min_paired_dates=5,
    )  # fmt: skip
    base.update(kw)
    return default_config("stocks", **base)


def pm_cfg(**kw) -> ExperimentConfig:
    base = dict(  # noqa: C408
        name="p", knowledge_mode="reconstructed_history", assets=["0xa", "0xb"], settings=settings(),
        origin_start=utc(2024, 1, 1), origin_end=utc(2024, 2, 1), targets_as_of=utc(2024, 3, 1),
        context_length=72, min_context_observations=48, origin_stride=12, models=fast_models(),
        bootstrap_samples=200, min_paired_dates=5,
    )  # fmt: skip
    base.update(kw)
    return default_config("polymarket", **base)


@pytest.fixture
def market(tmp_path):
    db = MarketDB(tmp_path)
    cl = sessions("2022-10-01", "2023-12-31")
    db.add_stock("SPY", cl, random_walk(len(cl), 1))
    db.add_stock("QQQ", cl, random_walk(len(cl), 2))
    hrs = pd.date_range("2023-12-20", "2024-02-10", freq="h", tz="UTC")
    z = np.cumsum(np.random.default_rng(3).normal(0, 0.05, len(hrs))) - 0.5
    p = 1 / (1 + np.exp(-z))
    p[-30:] = 1.0  # converges to 1 at the end: logit must stay finite
    db.add_market("0xa", hrs, p, closing=utc(2024, 2, 5), outcome="YES", resolved_at=utc(2024, 2, 6))
    db.add_market("0xb", hrs[:600], np.full(600, 0.3), no_probs=np.full(600, 0.9), closing=utc(2024, 6, 1))
    return db


@pytest.fixture
def store(tmp_path):
    return research_store(tmp_path)


def run(db, store, cfg, factory=None, **kw):
    eid = store.create(cfg, NOW, "test")
    r = ExperimentRunner(db.factory, store, clock(), model_factory=factory or fake_factory(), commit_every=7)
    return eid, r, r.run(eid, **kw)


# ------------------------------------------------------------------ configuration
def test_config_requires_explicit_replay_mode_and_valid_values():
    with pytest.raises(ValueError):
        default_config("stocks", name="x", knowledge_mode="whatever", assets=["SPY"], settings=settings(),
                       origin_start=utc(2023, 1, 1), origin_end=utc(2023, 2, 1))  # fmt: skip
    cfg = stock_cfg()
    d = cfg.model_dump(mode="json")
    d.pop("knowledge_mode")
    with pytest.raises(ValueError):
        ExperimentConfig.model_validate(d)
    for bad in ({"horizons": [0]}, {"horizons": [1, 1]}, {"horizons": [2000]}, {"quantile_levels": [0.1, 0.9]},
                {"interval_levels": [0.85]}, {"origin_end": utc(2023, 1, 1)}, {"origin_stride": 0},
                {"reference_baseline": "nope"}, {"extra_latency_seconds": -1}):  # fmt: skip
        with pytest.raises(ValueError):
            stock_cfg(**bad)
    with pytest.raises(ValueError):
        stock_cfg(models=["timestral-1b"])
    with pytest.raises(ValueError):  # strict replay has no latency knob
        stock_cfg(knowledge_mode="strict_point_in_time", extra_latency_seconds=60)
    with pytest.raises(ValueError):  # Polymarket target is the YES token
        pm_cfg(outcome_side="NO")
    with pytest.raises(ValueError):  # model parameters must be explicit
        ExperimentConfig.model_validate({**d, "knowledge_mode": "reconstructed_history",
                                         "models": [{"name": "zero", "params": {}}]})  # fmt: skip


def test_config_serialisation_and_identity():
    cfg = stock_cfg()
    again = ExperimentConfig.from_json(cfg.to_json())
    assert again == cfg and again.config_hash() == cfg.config_hash()
    assert cfg.experiment_id.startswith("stocks-")
    assert stock_cfg(name="other name").experiment_id == cfg.experiment_id  # name is not identity
    for change in ({"horizons": [1, 5]}, {"knowledge_mode": "strict_point_in_time"}, {"device": "cpu"},
                   {"seed": 1}, {"context_length": 61}, {"origin_stride": 1}):  # fmt: skip
        assert stock_cfg(**change).experiment_id != cfg.experiment_id
    assert stock_cfg(models=[*fast_models(MODELS[:-1]), model_spec("linear_trend", window=30, **FAST)]
                     ).experiment_id != cfg.experiment_id  # fmt: skip
    payload = json.loads(cfg.to_json())
    for key in ("knowledge_mode", "availability", "price_field", "quantile_levels", "seed", "device", "models",
                "targets_as_of", "cutoff_delay_seconds", "context_length"):  # fmt: skip
        assert key in payload
    assert payload["price_field"] == "close" and payload["target"] == "log_return"
    assert "close + " in payload["availability"]["rule"] or "close" in payload["availability"]["rule"]


# ------------------------------------------------------------------ origins
def test_stock_origins_follow_the_exchange_calendar(market):
    cfg = stock_cfg(
        origin_start=utc(2023, 11, 20), origin_end=utc(2023, 11, 30), origin_stride=1, horizons=[1, 2]
    )
    with market.factory() as s:
        assets, _ = D.resolve_assets(s, cfg)
        grid = D.make_grid(cfg, utc(2022, 10, 1))
        b = D.OriginBuilder(s, cfg, grid)
        cand, _ = b.candidate_origins(assets[0], b.data_span(assets[0]))
        assert cand == sorted(cand)
        # Thanksgiving 2023-11-23 is not a session; 2023-11-24 closed early at 13:00 New York (18:00Z)
        assert pd.Timestamp("2023-11-23 21:00Z") not in cand
        assert pd.Timestamp("2023-11-24 18:00Z") in cand
        po = b.prepare_origin(assets[0], pd.Timestamp("2023-11-22 21:00Z"))
        assert po.status == "ok"
        assert po.target_timestamps == [pd.Timestamp("2023-11-24 18:00Z"), pd.Timestamp("2023-11-27 21:00Z")]
        assert po.cutoff == utc(2023, 11, 22, 21, 30)
        assert pd.Timestamp(po.timestamps[-1], tz="UTC") == pd.Timestamp("2023-11-22 21:00Z")
        assert len(po.values) == cfg.context_length
        assert (po.timestamps.astype("datetime64[ns]") <= np.datetime64("2023-11-22T21:30")).all()


def test_polymarket_origins_hourly_and_sample_availability(market):
    cfg = pm_cfg(origin_stride=1, horizons=[1, 6, 24])
    with market.factory() as s:
        assets, _ = D.resolve_assets(s, cfg)
        b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2023, 12, 1)))
        po = b.prepare_origin(assets[0], pd.Timestamp("2024-01-10 05:00Z"))
        assert po.status == "ok"
        assert po.cutoff == utc(2024, 1, 10, 5, 5)
        assert po.target_timestamps == [pd.Timestamp("2024-01-10 06:00Z"), pd.Timestamp("2024-01-10 11:00Z"),
                                        pd.Timestamp("2024-01-11 05:00Z")]  # fmt: skip
        assert pd.Timestamp(po.timestamps[-1], tz="UTC") == pd.Timestamp("2024-01-10 05:00Z")
        # the 05:00 bucket is sampled at 05:00:20 and available at 05:01:20: with a cutoff at
        # 05:01:00 it is not yet usable, so the origin has no observation of its own
        late = pm_cfg(origin_stride=1, cutoff_delay_seconds=60)
        b2 = D.OriginBuilder(s, late, D.make_grid(late, utc(2023, 12, 1)))
        assert (
            b2.prepare_origin(assets[0], pd.Timestamp("2024-01-10 05:00Z")).reason
            == "origin_observation_missing"
        )
        # the YES token price is used, never the NO token's
        b_ = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2023, 12, 1)))
        pb = b_.prepare_origin(assets[1], pd.Timestamp("2024-01-10 05:00Z"))
        assert pb.last_level == pytest.approx(0.3)


def test_minimum_context_is_enforced(market):
    cfg = pm_cfg(origin_stride=1)
    with market.factory() as s:
        assets, _ = D.resolve_assets(s, cfg)
        b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2023, 12, 1)))
        # data starts 2023-12-20 00:00: 30 hours later there are only 31 points (< 48)
        assert b.prepare_origin(assets[0], pd.Timestamp("2023-12-21 06:00Z")).reason == "insufficient_context"
        assert b.prepare_origin(assets[0], pd.Timestamp("2023-12-22 06:00Z")).status == "ok"


def test_planted_future_values_never_reach_the_context(market):
    """A huge spike after the cutoff, and a correction of an in-context bar retrieved later, must
    not change the context at the origin (no look-ahead)."""
    cfg = stock_cfg(origin_stride=1)
    t_o = pd.Timestamp("2023-07-03 17:00Z")  # early close before Independence Day
    with market.factory() as s:
        assets, _ = D.resolve_assets(s, cfg)
        b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2022, 10, 1)))
        before = b.prepare_origin(assets[0], t_o)
    spike_day = sessions("2023-07-05", "2023-07-05")
    corr_day = sessions("2023-06-30", "2023-06-30")
    market.add_stock_records(
        "SPY", stock_records("SPY", spike_day, [1e6], retrieved=BACKFILLED + timedelta(days=1))
    )
    market.add_stock_records(
        "SPY", stock_records("SPY", corr_day, [1.0], retrieved=BACKFILLED + timedelta(days=2))
    )
    with market.factory() as s:
        b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2022, 10, 1)))
        after = b.prepare_origin(assets[0], t_o)
    assert after.input_hash == before.input_hash
    assert np.array_equal(after.values, before.values)
    assert np.abs(after.values).max() < 0.2


def test_missing_targets_are_never_filled(market):
    def statuses(targets_as_of):
        cfg = stock_cfg(origin_stride=1, horizons=[1], targets_as_of=targets_as_of)
        with market.factory() as s:
            assets, _ = D.resolve_assets(s, cfg)
            b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2022, 10, 1)))
            real = b.realised(assets[0], pd.Timestamp("2023-12-27 21:00Z"), pd.Timestamp("2024-01-05 21:00Z"))
        assert real[real["status"] != "observed"]["value"].isna().all()  # never filled
        return dict(zip(real["target_ts"], real["status"], strict=True))

    # data ends 2023-12-29. Read on 2024-01-02 at noon, the 2 January bar is not known yet ...
    st = statuses(utc(2024, 1, 2, 12))
    assert st[pd.Timestamp("2023-12-29 21:00Z")] == "observed"
    assert st[pd.Timestamp("2024-01-02 21:00Z")] == "target_not_yet_available"
    # ... read a month later it should exist and does not: it is missing, not repaired
    st = statuses(utc(2024, 2, 1))
    assert st[pd.Timestamp("2024-01-02 21:00Z")] == "target_missing"
    # a session whose previous close is missing has no return either (no return across a gap)
    assert st[pd.Timestamp("2024-01-03 21:00Z")] == "target_missing"


# ------------------------------------------------------------------ replay integration
def test_replay_mode_dispatch_is_explicit(market, monkeypatch):
    calls = []
    orig_strict, orig_rec = D.get_history, D.get_reconstructed_history
    monkeypatch.setattr(D, "get_history", lambda *a, **k: calls.append("strict") or orig_strict(*a, **k))
    monkeypatch.setattr(
        D, "get_reconstructed_history", lambda *a, **k: calls.append("rec") or orig_rec(*a, **k)
    )
    with market.factory() as s:
        D.read_history(s, KnowledgeMode.STRICT, 1, NOW, "1d", "yfinance")
        D.read_history(s, KnowledgeMode.RECONSTRUCTED, 1, NOW, "1d", "yfinance")
        assert calls == ["strict", "rec"]
        with pytest.raises(ValueError):
            D.read_history(s, KnowledgeMode.STRICT, 1, NOW, "1d", "yfinance", extra_latency=timedelta(1))
        # an accessor answering in the wrong mode is refused (modes are never mixed)
        monkeypatch.setattr(D, "get_history", lambda *a, **k: orig_rec(*a, **k))
        with pytest.raises(D.ReplayModeMismatch):
            D.read_history(s, KnowledgeMode.STRICT, 1, NOW, "1d", "yfinance")


def test_strict_experiment_sees_nothing_that_was_only_backfilled(market, store):
    cfg = stock_cfg(knowledge_mode="strict_point_in_time")
    eid, _r, res = run(market, store, cfg)
    prep = store.get(eid).prepare
    assert all(a["ok_origins"] == 0 for a in prep["assets"].values())
    assert res["status"] == "completed"  # nothing to forecast is a valid, reported outcome
    assert A.load_scored(store, eid).rows.empty


def test_strict_experiment_uses_data_captured_in_time(tmp_path, store):
    db = MarketDB(tmp_path)
    cl = sessions("2022-10-01", "2023-12-31")
    # each bar retrieved one hour after its availability: genuinely known in time
    recs = [r for r in stock_records("SPY", cl, random_walk(len(cl), 5))]
    db.add_stock("SPY", cl[:0], [])
    for r in recs:
        object.__setattr__(r, "retrieved_at", r.available_at + timedelta(hours=1))
    db.add_stock_records("SPY", recs)
    cfg = stock_cfg(knowledge_mode="strict_point_in_time", assets=["SPY"], cutoff_delay_seconds=1800 + 3600)
    eid, r, _res = run(db, store, cfg)
    sc = A.load_scored(store, eid)
    assert not sc.rows.empty
    with sqlite3.connect(tmp_path / "research.sqlite3") as c:
        prov = [
            json.loads(p)
            for (p,) in c.execute("select provenance_json from research_origins where status='ok'")
        ]
    assert all(p["knowledge_mode"] == "strict_point_in_time" and p["reconstructed"] == 0 for p in prov)


def test_extra_replay_latency_is_respected(market):
    cfg = stock_cfg(extra_latency_seconds=3600)  # bar known 30 min + 1 h after the close
    with market.factory() as s:
        assets, _ = D.resolve_assets(s, cfg)
        b = D.OriginBuilder(s, cfg, D.make_grid(cfg, utc(2022, 10, 1)))
        po = b.prepare_origin(assets[0], pd.Timestamp("2023-08-01 20:00Z"))
    assert po.reason == "origin_observation_missing"  # cutoff close + 30 min < close + 90 min


def test_reconstructed_provenance_is_preserved(market, store):
    eid, _r, _res = run(market, store, stock_cfg(models=fast_models(["zero"]), reference_baseline="zero"))
    with sqlite3.connect(Path(store.engine.url.database)) as c:
        prov = json.loads(
            c.execute("select provenance_json from research_origins where status='ok' limit 1").fetchone()[0]
        )
        knowledge = {k for (k,) in c.execute("select distinct knowledge from research_targets")}
    assert prov["knowledge_mode"] == "reconstructed_history" and prov["reconstructed"] > 0
    assert prov["sources"] == ["yfinance"]
    assert knowledge == {"reconstructed"}
    assert store.get(eid).config.availability["rule"]


def test_research_package_reads_observations_only_through_replay_accessors():
    """No module in mpe.research queries the observations table except the descriptive asset
    listing; forecasting inputs and targets come from get_history / get_reconstructed_history."""
    pkg = ROOT / "src" / "mpe" / "research"
    for p in pkg.glob("*.py"):
        tree = ast.parse(p.read_text())
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
            if "Observation" in names:
                assert (p.name, fn.name) == ("data.py", "describe_assets"), (
                    f"{p.name}:{fn.name} queries observations"
                )


# ------------------------------------------------------------------ execution
def test_end_to_end_all_baselines_and_fake_timestral(market, store):
    eid, _r, res = run(market, store, stock_cfg())
    assert res["status"] == "completed"
    assert set(res["models"]) == set(MODELS)
    # models were loaded one at a time and each was unloaded
    assert FakeTimestral.loads == ["timestral-5m", "timestral-209m"]
    assert FakeTimestral.unloads == FakeTimestral.loads and not FakeTimestral.resident
    sc = A.load_scored(store, eid)
    counts = sc.rows.groupby("model").size()
    assert set(counts.index) == set(MODELS) and counts.nunique() == 1  # common sample for all models
    lb = A.leaderboard(sc)
    zero = lb[lb["model"] == "zero"]
    assert (zero["rel_mae"].abs() < 1e-12).all()
    assert set(lb["horizon"]) == {1, 5, 20}
    runs = store.model_runs(eid)
    assert {x["model_name"] for x in runs} == set(MODELS)
    assert all(x["status"] == "completed" and x["device"] == "cpu" for x in runs)
    assert store.get(eid).model_versions["timestral-5m"] == "fake-rev-1"


def test_reproducible_metrics(tmp_path, market):
    s1 = ResearchStore(make_research_engine(tmp_path / "a.sqlite3"))
    s2 = ResearchStore(make_research_engine(tmp_path / "b.sqlite3"))
    e1, *_ = run(market, s1, stock_cfg())
    e2, *_ = run(market, s2, stock_cfg())
    assert e1 == e2
    l1, l2 = A.leaderboard(A.load_scored(s1, e1)), A.leaderboard(A.load_scored(s2, e2))
    pd.testing.assert_frame_equal(l1, l2)


def test_invalid_outputs_and_model_errors_are_recorded(market, store):
    bad = {"2023-06-08 20:00:00+00:00"}  # EDT: the session closes at 20:00Z
    fail = {"2023-06-15 20:00:00+00:00"}
    factory = fake_factory(**{"timestral-5m": {"bad_output_on": bad, "fail_on": fail}})
    eid, _r, res = run(market, store, stock_cfg(), factory=factory)
    assert res["models"]["timestral-5m"]["failed"] == 4  # 2 assets x 2 origins
    sc = A.load_scored(store, eid)
    assert sc.exclusions["forecast_failures"] == {"timestral-5m": 4}
    errs = {e["error"].split(":")[0] for e in sc.exclusions["failure_examples"]["timestral-5m"]}
    assert errs <= {"AssertionError", "RuntimeError"} and "AssertionError" in errs
    # failed origins leave the common sample for every model, and are counted
    assert sc.exclusions["origins_without_all_models"] == 4
    assert sc.rows.groupby("model").size().nunique() == 1


def test_interrupted_run_resumes_without_duplicates(market, store):
    calls = {"n": 0}
    base = fake_factory()

    class Boom(FakeTimestral):
        def forecast(self, data):
            calls["n"] += 1
            if calls["n"] == 9:
                raise KeyboardInterrupt
            return super().forecast(data)

    def factory(spec):
        return Boom(spec.name) if spec.name == "timestral-209m" else base(spec)

    cfg = stock_cfg()
    eid = store.create(cfg, NOW, "test")
    r = ExperimentRunner(market.factory, store, clock(), model_factory=factory, commit_every=3)
    with pytest.raises(KeyboardInterrupt):
        r.run(eid)
    assert store.get(eid).status == "interrupted"
    assert not FakeTimestral.resident  # unloaded even when interrupted
    done_before = len(store.done_forecasts(eid, "timestral-209m"))
    assert done_before == 8
    # a restarted process with a fresh store object resumes where it stopped
    store2 = ResearchStore(store.engine)
    r2 = ExperimentRunner(market.factory, store2, clock(), model_factory=fake_factory())
    res = r2.run(eid)
    assert res["status"] == "completed"
    assert res["models"]["timestral-209m"]["new"] == len(r2.prepare(eid).ok) - done_before
    assert res["models"]["timestral-5m"]["new"] == 0
    with sqlite3.connect(Path(store.engine.url.database)) as c:
        n, d = c.execute(
            "select count(*), count(distinct model_name||asset||origin_ts) from research_forecasts"
        ).fetchone()
    assert n == d
    assert [x["status"] for x in store2.model_runs(eid) if x["model_name"] == "timestral-209m"] == [
        "interrupted",
        "completed",
    ]


def test_batches_and_duplicate_execution(market, store):
    cfg = stock_cfg(models=fast_models(["zero", "persistence"]), reference_baseline="zero")
    eid, r, res = run(market, store, cfg, max_forecasts=10)
    assert res["status"] == "partial"
    assert res["models"]["zero"]["new"] == 10 and "persistence" not in res["models"]
    res = r.run(eid)
    assert res["status"] == "completed"
    total = len(r.prepare(eid).ok)
    assert res["models"]["zero"]["new"] == total - 10
    again = r.run(eid)  # a duplicate execution adds nothing
    assert all(v["new"] == 0 for v in again["models"].values()) and again["status"] == "completed"
    assert len(store.done_forecasts(eid, "zero")) == total


def test_configuration_survives_restart_and_ids_do_not_collide(tmp_path, market):
    path = tmp_path / "r.sqlite3"
    s = ResearchStore(make_research_engine(path))
    cfg = stock_cfg()
    eid = s.create(cfg, NOW, "test")
    with pytest.raises(ExperimentExists):
        s.create(stock_cfg(name="same config, other name"), NOW, "test")
    other = s.create(stock_cfg(horizons=[1]), NOW, "test")
    assert other != eid
    s2 = ResearchStore(make_research_engine(path))
    assert s2.get(eid).config == cfg
    assert {e["experiment_id"] for e in s2.list()} == {eid, other}


def test_stored_results_are_immutable(market, store):
    _eid, *_ = run(market, store, stock_cfg(models=fast_models(["zero"]), reference_baseline="zero"))
    db = Path(store.engine.url.database)
    with sqlite3.connect(db) as c:
        for sql in ("update research_forecasts set status='ok'", "delete from research_forecasts",
                    "update research_origins set status='ok'", "delete from research_targets"):  # fmt: skip
            with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                c.execute(sql)


def test_changed_data_is_detected_on_resume(market, store):
    cfg = stock_cfg(models=fast_models(["zero", "persistence"]), reference_baseline="zero")
    eid, r, _ = run(market, store, cfg, max_forecasts=5)
    with market.factory() as s:
        from mpe.storage.orm import Observation

        s.query(Observation).filter(Observation.timestamp == utc(2023, 6, 1, 20)).delete()  # test DB only
        s.commit()
    with pytest.raises(DataChanged):
        r.run(eid)


def test_model_version_change_is_refused(market, store):
    cfg = stock_cfg(models=fast_models(["timestral-5m", "zero"]), reference_baseline="zero")
    eid, _r, _ = run(market, store, cfg, max_forecasts=4)
    r2 = ExperimentRunner(market.factory, store, clock(),
                          model_factory=fake_factory(**{"timestral-5m": {"version": "fake-rev-2"}}))  # fmt: skip
    res = r2.run(eid)
    assert res["models"]["timestral-5m"]["status"] == "failed"
    assert "VersionChanged" in res["models"]["timestral-5m"]["error"]
    runs = store.model_runs(eid)
    assert runs[-2]["status"] == "failed" and "VersionChanged" in runs[-2]["error"]  # diagnostics kept
    _ = VersionChanged


def test_failed_model_load_keeps_diagnostics(market, store):
    base = fake_factory()

    def factory(spec):
        if spec.name == "timestral-5m":
            m = FakeTimestral(spec.name)
            m.load = lambda device="auto": (_ for _ in ()).throw(OSError("weights missing"))
            return m
        return base(spec)

    cfg = stock_cfg(models=fast_models(["timestral-5m", "zero"]), reference_baseline="zero")
    eid, _r, res = run(market, store, cfg, factory=factory)
    assert res["models"]["timestral-5m"]["status"] == "failed"
    assert res["models"]["zero"]["status"] == "completed"  # the next model still runs
    assert res["status"] == "failed"
    assert store.get(eid).status == "failed"
    run5 = next(x for x in store.model_runs(eid) if x["model_name"] == "timestral-5m")
    assert "weights missing" in run5["error"]


# ------------------------------------------------------------------ evaluation
def test_polymarket_experiment_probability_space_and_resolution(market, store):
    eid, _r, res = run(market, store, pm_cfg())
    assert res["status"] == "completed"
    sc = A.load_scored(store, eid)
    assert {"mae_p", "rmse_p"} <= set(A.leaderboard(sc).columns)
    assert ((sc.rows["phat"] > 0) & (sc.rows["phat"] < 1)).all()
    assert ((sc.rows["p"] > 0) & (sc.rows["p"] < 1)).all()
    # no target after the scheduled close of 0xa (2024-02-05)
    a = sc.rows[sc.rows["asset"] == "0xa"]
    assert (a["target_ts"] <= pd.Timestamp("2024-02-05", tz="UTC")).all()
    rs = A.resolution_analysis(sc)
    assert rs["applicable"] and rs["n_markets"] == 1 and rs["outcomes"] == {"YES": 1, "NO": 0}
    # persistence is the reference for market prices
    lb = A.leaderboard(sc)
    assert (lb[lb["model"] == "persistence"]["rel_mae"].abs() < 1e-12).all()


def test_paired_comparisons_and_small_sample_label(market, store):
    eid, *_ = run(
        market,
        store,
        stock_cfg(origin_stride=1, models=fast_models(["timestral-5m", "zero", "moving_average"])),
    )
    sc = A.load_scored(store, eid)
    same = A.paired(sc, "zero", "zero", 1, "mae")
    assert same["mean_diff"] == 0 and same["ci_low"] == 0 and same["ci_high"] == 0
    assert same["conclusion"] == "no demonstrated difference"
    tiny = A.paired(sc, "timestral-5m", "zero", 20, "crps", df=sc.rows[sc.rows["origin_ts"] < "2023-06-20"])
    assert tiny["conclusion"] == "insufficient data"
    cmp_ = A.comparisons(sc, A.leaderboard(sc))
    assert set(cmp_["against"]) <= {"reference", "best baseline"}
    assert {"n_pairs", "n_assets", "n_dates", "rel_improvement", "conclusion"} <= set(cmp_.columns)


def test_pooled_and_macro_aggregation_differ_with_unbalanced_assets(market, store):
    cfg = stock_cfg(models=fast_models(["zero", "persistence"]), reference_baseline="zero")
    eid, *_ = run(market, store, cfg)
    sc = A.load_scored(store, eid)
    sc.rows = sc.rows[~((sc.rows["asset"] == "QQQ") & (sc.rows["origin_ts"] > "2023-07-01"))].reset_index(
        drop=True
    )
    sc.below = sc.below[: len(sc.rows)]
    lb = A.leaderboard(sc)
    r = lb[(lb["model"] == "persistence") & (lb["horizon"] == 1)].iloc[0]
    g = sc.rows[(sc.rows["model"] == "persistence") & (sc.rows["horizon"] == 1)]
    assert r["mae"] == pytest.approx(g["abs_err"].mean())
    assert r["macro_mae"] == pytest.approx(g.groupby("asset")["abs_err"].mean().mean())
    assert r["mae"] != pytest.approx(r["macro_mae"])


def test_report_is_written_once_and_labelled(tmp_path, market, store):
    eid, *_ = run(market, store, stock_cfg())
    out = write_report(store, eid, root=tmp_path / "reports")
    md = (out / "report.md").read_text()
    assert "RECONSTRUCTED RESEARCH" in md and "Paired comparisons" in md and "Calibration" in md
    for f in ("config.json", "summary.json", "leaderboard.csv", "calibration.csv", "over_time.csv"):
        assert (out / f).exists()
    assert list(out.glob("*.svg"))
    before = (out / "report.md").stat().st_mtime_ns
    assert write_report(store, eid, root=tmp_path / "reports") == out
    assert (out / "report.md").stat().st_mtime_ns == before  # not rewritten


def test_asset_skill_is_scale_free(market, store):
    cfg = stock_cfg(models=fast_models(["zero", "persistence"]), reference_baseline="zero")
    eid, *_ = run(market, store, cfg)
    sc = A.load_scored(store, eid)
    lb = A.leaderboard(sc)
    r = lb[(lb["model"] == "persistence") & (lb["horizon"] == 1)].iloc[0]
    g = sc.rows[sc.rows["horizon"] == 1].groupby(["asset", "model"])["abs_err"].mean().unstack()
    assert r["asset_skill_mae"] == pytest.approx((1 - g["persistence"] / g["zero"]).mean())
    # multiplying one asset's errors by 100 leaves its skill, and the average skill, unchanged
    sc.rows.loc[sc.rows["asset"] == "QQQ", ["abs_err", "crps"]] *= 100
    lb2 = A.leaderboard(sc)
    r2 = lb2[(lb2["model"] == "persistence") & (lb2["horizon"] == 1)].iloc[0]
    assert r2["asset_skill_mae"] == pytest.approx(r["asset_skill_mae"])
    cmp_ = A.comparisons(A.load_scored(store, eid), lb)
    assert cmp_.empty or "dm_p_holm" in cmp_
