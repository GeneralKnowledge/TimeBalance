"""``mpe research`` CLI on offline fixtures."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from tests.research_fakes import NOW, FakeTimestral, MarketDB, clock, random_walk, sessions

from mpe import main as cli
from mpe.research import runner as runner_mod


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = MarketDB(tmp_path)
    cl = sessions("2022-10-01", "2023-12-31")
    db.add_stock("SPY", cl, random_walk(len(cl), 1))
    db.add_stock("QQQ", cl, random_walk(len(cl), 2))
    hrs = pd.date_range("2023-12-20", "2024-02-10", freq="h", tz="UTC")
    db.add_market("0xa", hrs, 1 / (1 + np.exp(-np.sin(np.arange(len(hrs)) / 30))))
    reports = tmp_path / "reports"
    monkeypatch.setattr("mpe.research.report.REPORTS", reports)
    monkeypatch.setattr(runner_mod, "default_model_factory", _fake_or_real)
    monkeypatch.setattr(runner_mod.ExperimentRunner.__init__, "__defaults__",
                        (_fake_or_real, None, 100))  # fmt: skip
    base = ["research", "--market-db", str(db.path), "--research-db", str(tmp_path / "r.sqlite3")]
    return base, reports, db


def _fake_or_real(spec):
    from mpe.models.baselines import BASELINES

    if spec.family == "timestral":
        return FakeTimestral(spec.name)
    return BASELINES[spec.name](**spec.params)


def mpe(argv, capsys) -> tuple[int, str, str]:
    rc = cli.main(argv, clock=clock())
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_assets_listing(env, capsys):
    base, _, _ = env
    rc, out, _ = mpe([*base, "assets", "--domain", "stocks"], capsys)
    assert rc == 0 and "SPY" in out and "QQQ" in out
    rc, out, _ = mpe([*base, "assets", "--domain", "polymarket", "--json"], capsys)
    rows = json.loads(out)
    assert rows[0]["key"] == "0xa" and rows[0]["observations"] > 1000 and rows[0]["first"].startswith("2023-12-20")


def test_create_run_show_report_export(env, capsys, tmp_path):
    base, reports, _ = env
    create = [*base, "create", "--domain", "stocks", "--mode", "reconstructed", "--assets", "SPY,QQQ",
              "--start", "2023-06-01", "--end", "2023-08-31", "--targets-as-of", "2023-12-01", "--context", "60",
              "--models", "timestral-5m,zero,persistence", "--stride", "5"]  # fmt: skip
    rc, out, err = mpe(create, capsys)
    eid = out.strip()
    assert rc == 0 and eid.startswith("stocks-") and "reconstructed research" in err
    rc, out, _ = mpe(create, capsys)  # same configuration: not duplicated
    assert "already exists" in out
    rc, out, _ = mpe([*base, "list"], capsys)
    assert eid in out and "created" in out
    rc, out, err = mpe([*base, "run", eid, "--max-forecasts", "5"], capsys)
    assert rc == 2 and "partial" in out  # a resumable batch
    rc, out, err = mpe([*base, "run", eid], capsys)
    assert rc == 0 and f"experiment {eid}: completed" in out
    rc, out, _ = mpe([*base, "show", eid], capsys)
    assert "RECONSTRUCTED RESEARCH" in out and "timestral-5m" in out and "rel_mae" in out
    for section in ("models", "horizons", "assets", "calibration", "comparisons", "exclusions", "runs", "config"):
        rc, out, _ = mpe([*base, "show", eid, "--section", section], capsys)
        assert rc == 0 and out.strip()
    rc, out, _ = mpe([*base, "show", eid, "--json"], capsys)
    assert json.loads(out)["status"] == "completed"
    rc, out, _ = mpe([*base, "report", eid], capsys)
    path = out.strip()
    assert path.startswith(str(reports / eid)) and (reports / eid).exists()
    rc, out, _ = mpe([*base, "export", eid, "--format", "csv", "--out", str(tmp_path / "x")], capsys)
    f = pd.read_csv(tmp_path / "x" / "forecasts.csv")
    assert {"model", "asset", "origin_ts", "horizon", "target_ts", "median", "q0.5", "q0.99"} <= set(f.columns)
    assert len(f) == 3 * f[["model", "asset", "origin_ts"]].drop_duplicates().shape[0]
    rc, out, _ = mpe([*base, "export", eid, "--format", "json", "--out", str(tmp_path / "j")], capsys)
    assert json.loads((tmp_path / "j" / "leaderboard.json").read_text())
    with pytest.raises(SystemExit):  # never overwrites an export
        mpe([*base, "export", eid, "--format", "csv", "--out", str(tmp_path / "x")], capsys)


def test_polymarket_create_defaults(env, capsys):
    base, _, _ = env
    rc, out, _ = mpe([*base, "create", "--domain", "polymarket", "--mode", "strict", "--start", "2024-01-05",
                      "--end", "2024-01-20", "--targets-as-of", "2024-02-01", "--models", "zero", "--print"], capsys)  # fmt: skip
    cfg = json.loads(out)
    assert cfg["knowledge_mode"] == "strict_point_in_time" and cfg["assets"] == ["0xa"]
    assert cfg["horizons"] == [1, 6, 24] and cfg["target"] == "logit_price" and cfg["outcome_side"] == "YES"
    assert {m["name"] for m in cfg["models"]} == {"zero", "persistence"}  # the reference is always included


def test_invalid_arguments(env, capsys):
    base, _, _ = env
    with pytest.raises(SystemExit):
        mpe([*base, "create", "--domain", "stocks"], capsys)  # no replay mode
    with pytest.raises(SystemExit):
        mpe([*base, "create", "--domain", "stocks", "--mode", "live"], capsys)
    with pytest.raises(SystemExit):
        mpe([*base, "create", "--domain", "stocks", "--mode", "strict", "--models", "gpt"], capsys)
    with pytest.raises(ValueError):
        mpe([*base, "create", "--domain", "stocks", "--mode", "strict", "--horizons", "0"], capsys)
    with pytest.raises(KeyError):
        mpe([*base, "show", "stocks-000000000000"], capsys)


def test_market_database_is_opened_read_only(env, tmp_path):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from mpe.research.store import make_readonly_market_engine

    _, _, db = env
    eng = make_readonly_market_engine(db.path)
    with eng.connect() as c:
        assert c.execute(text("select count(*) from observations")).scalar() > 0
        with pytest.raises(OperationalError):
            c.execute(text("delete from observations"))
    _ = NOW
