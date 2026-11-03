"""`mpe ingest` always finalises its job_runs row, whatever fails (providers mocked, temp DB)."""

import json

import pytest
from sqlalchemy import select

from mpe.clock import FixedClock
from mpe.data.ingestion import Ingestor, RunReport, UnitResult
from mpe.data.providers.polymarket import PolymarketProvider
from mpe.data.providers.yahoo import YahooProvider
from mpe.main import main
from mpe.storage import repositories as R
from mpe.storage.database import make_engine, session_factory
from mpe.storage.orm import JobRun
from tests.fakes import T0


@pytest.fixture
def cli(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite3"
    monkeypatch.setenv("MPE_DATABASE", str(path))
    clock = FixedClock(T0)

    def ok_report(self, *a, **k):
        return RunReport([UnitResult("fake:unit", True, {"inserted": 1})])

    monkeypatch.setattr(Ingestor, "update_stocks", ok_report)
    monkeypatch.setattr(Ingestor, "update_polymarket", ok_report)

    def jobs():
        with session_factory(make_engine(path))() as s:
            return list(s.scalars(select(JobRun).order_by(JobRun.id)))

    return clock, jobs


def run(clock, only="stocks"):
    return main(["ingest", "update", "--only", only], clock=clock)


def test_success_keeps_succeeded_state(cli):
    clock, jobs = cli
    assert run(clock) == 0
    (j,) = jobs()
    assert (j.status, j.error) == ("succeeded", None) and j.finished_at is not None
    assert json.loads(j.stats_json)["units"] == 1


def test_provider_construction_failure_marks_job_failed(cli, monkeypatch):
    clock, jobs = cli

    def broken(self, *a, **k):
        raise RuntimeError("cannot build provider")

    monkeypatch.setattr(YahooProvider, "__init__", broken)
    with pytest.raises(RuntimeError, match="cannot build provider"):
        run(clock)
    (j,) = jobs()
    assert j.status == "failed" and j.finished_at is not None
    assert j.error == "RuntimeError: cannot build provider"


def test_ingestion_exception_marks_job_failed_and_propagates(cli, monkeypatch):
    clock, jobs = cli

    def boom(self, *a, **k):
        raise ValueError("ingestion blew up")

    monkeypatch.setattr(Ingestor, "update_stocks", boom)
    with pytest.raises(ValueError, match="ingestion blew up"):
        run(clock)
    (j,) = jobs()
    assert j.status == "failed" and "ValueError: ingestion blew up" in j.error


def test_unit_failure_marks_job_failed(cli, monkeypatch):
    clock, jobs = cli
    monkeypatch.setattr(Ingestor, "update_stocks",
                        lambda self, *a: RunReport([UnitResult("yfinance:SPY", False, error="HTTP 503")]))  # fmt: skip
    assert run(clock) == 1
    (j,) = jobs()
    assert j.status == "failed" and j.error == "yfinance:SPY: HTTP 503"


def test_budget_flush_failure_does_not_prevent_finalisation(cli, monkeypatch):
    clock, jobs = cli

    def flush_fails(self):
        raise OSError("disk full")

    monkeypatch.setattr(R.DbRequestBudget, "flush", flush_fails)
    assert run(clock, only="polymarket") == 1  # work done, but cleanup failed: not a success
    (j,) = jobs()
    assert j.status == "failed" and j.finished_at is not None
    assert "budget.flush: OSError: disk full" in j.error
    assert json.loads(j.stats_json)["cleanup_errors"] == ["budget.flush: OSError: disk full"]


def test_flush_failure_after_ingestion_error_keeps_original_error(cli, monkeypatch):
    clock, jobs = cli
    closed = []

    def boom(self, *a, **k):
        raise ValueError("original")

    def flush_fails(self):
        raise OSError("disk full")

    monkeypatch.setattr(Ingestor, "update_polymarket", boom)
    monkeypatch.setattr(R.DbRequestBudget, "flush", flush_fails)
    monkeypatch.setattr(PolymarketProvider, "close", lambda self: closed.append(True))
    with pytest.raises(ValueError, match="original"):  # not masked by the cleanup error
        run(clock, only="polymarket")
    assert closed == [True]  # later cleanup steps still ran
    (j,) = jobs()
    assert j.status == "failed"
    assert j.error.startswith("ValueError: original") and "budget.flush: OSError" in j.error


def test_other_cleanup_failure_still_flushes_budget_and_finalises(cli, monkeypatch):
    clock, jobs = cli
    flushed = []
    real_flush = R.DbRequestBudget.flush

    def close_fails(self):
        raise RuntimeError("socket stuck")

    monkeypatch.setattr(PolymarketProvider, "close", close_fails)
    monkeypatch.setattr(R.DbRequestBudget, "flush", lambda self: (flushed.append(True), real_flush(self)))
    assert run(clock, only="polymarket") == 1
    assert flushed == [True]
    (j,) = jobs()
    assert j.status == "failed" and "polymarket.close: RuntimeError: socket stuck" in j.error


def test_finalisation_failure_does_not_mask_ingestion_error(cli, monkeypatch):
    clock, jobs = cli

    def boom(self, *a, **k):
        raise ValueError("original")

    def finish_fails(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(Ingestor, "update_stocks", boom)
    monkeypatch.setattr(R, "finish_job", finish_fails)
    with pytest.raises(ValueError, match="original"):
        run(clock)
    assert jobs()[0].status == "running"  # could not be written; the exception says why


def test_finalisation_failure_after_success_is_raised(cli, monkeypatch):
    clock, _ = cli

    def finish_fails(*a, **k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(R, "finish_job", finish_fails)
    with pytest.raises(RuntimeError, match="locked"):  # never reported as a silent success
        run(clock)


def test_failed_slot_is_retried_and_can_then_succeed(cli, monkeypatch):
    clock, jobs = cli

    def boom(self, *a, **k):
        raise ValueError("transient")

    with monkeypatch.context() as m:
        m.setattr(Ingestor, "update_stocks", boom)
        with pytest.raises(ValueError):
            run(clock)
    assert run(clock) == 0
    (j,) = jobs()
    assert (j.status, j.error) == ("succeeded", None)
