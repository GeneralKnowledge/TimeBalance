"""CLI entry point ``mpe``.

mpe db init                         create / migrate the SQLite schema
mpe ingest backfill [--only stocks|polymarket] [--symbols SPY,QQQ]
mpe ingest update   [--only stocks|polymarket] [--slot-minutes 30]
mpe data health     [--json]
mpe models list
mpe research ...                    M2 forecasting research (see ``mpe research -h``)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from mpe.clock import Clock, SystemClock, to_iso

log = logging.getLogger("mpe")


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"t": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                           "logger": record.name, "run_id": self.run_id, "msg": record.getMessage()})  # fmt: skip


def _setup_logging(verbose: bool, json_logs: bool, run_id: str) -> None:
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(
        JsonFormatter(run_id) if json_logs else logging.Formatter("%(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, handlers=[h], force=True)
    for noisy in ("httpx", "yfinance", "peewee", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _context(clock: Clock):
    from mpe.config import load_assets, load_settings
    from mpe.storage.database import make_engine, session_factory, upgrade

    settings = load_settings()  # refuses real_trading_enabled: true
    engine = make_engine(settings.resolve(settings.database_path))
    upgrade(engine)
    return settings, load_assets(), engine, session_factory(engine)


def _slot(now: datetime, minutes: int) -> str:
    m = (now.hour * 60 + now.minute) // minutes * minutes
    return now.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")


def cmd_ingest(args, clock: Clock) -> int:
    from mpe.data.ingestion import Ingestor, RawDump, RunReport
    from mpe.data.providers.polymarket import PolymarketProvider
    from mpe.data.providers.yahoo import YahooProvider
    from mpe.storage import repositories as R

    settings, assets, _engine, factory = _context(clock)
    now = clock.now()
    which = [args.only] if args.only else ["stocks", "polymarket"]
    job_name = f"ingest_{args.action}_{'_'.join(which)}"
    scheduled = _slot(now, args.slot_minutes) if args.action == "update" else f"manual:{to_iso(now)}"
    try:
        job_id = R.start_job(factory, job_name, scheduled, now)
    except R.JobAlreadyDone as e:
        print(f"skip: {e}")
        return 0
    # Once the job is claimed every exit path finalises it: provider construction, ingestion and
    # cleanup all run inside the try, cleanup steps are isolated from each other, and a failure
    # to finalise never hides the original exception.
    report = RunReport()
    budget = raw = pm = yh = None
    error: str | None = None
    cleanup_errors: list[str] = []
    try:
        budget = R.DbRequestBudget(factory, clock, {"polymarket": settings.polymarket.daily_request_budget})
        if args.raw_dump:
            raw = RawDump(settings.resolve(settings.raw_dump_dir), clock, "polymarket")
        pm = PolymarketProvider(settings, clock, budget, on_raw=raw) if "polymarket" in which else None
        yh = YahooProvider(settings, assets, clock) if "stocks" in which else None
        ing = Ingestor(settings, assets, clock, factory, yahoo=yh, polymarket=pm)
        symbols = args.symbols.split(",") if args.symbols else None
        if yh:
            sub = ing.backfill_stocks(symbols) if args.action == "backfill" else ing.update_stocks(symbols)
            report.results += sub.results
        if pm:
            sub = ing.backfill_polymarket() if args.action == "backfill" else ing.update_polymarket()
            report.results += sub.results
    except BaseException as e:  # record (Ctrl-C included), finalise below, then re-raise
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        for step, fn in (("budget.flush", budget and budget.flush), ("polymarket.close", pm and pm.close),
                         ("raw_dump.close", raw and raw.close)):  # fmt: skip
            if fn is None:
                continue
            try:
                fn()
            except Exception as ce:  # every cleanup step must get its turn
                cleanup_errors.append(f"{step}: {type(ce).__name__}: {ce}")
                log.exception("cleanup step %s failed for job_run %s", step, job_id)
        stats = report.as_dict()
        stats["requests"] = {"polymarket": pm.http.requests if pm else 0}
        if cleanup_errors:
            stats["cleanup_errors"] = cleanup_errors
        status = "failed" if error or report.failed or cleanup_errors else "succeeded"
        parts = [error] if error else ["; ".join(f"{r.unit}: {r.error}" for r in report.failed)]
        parts += [f"cleanup {c}" for c in cleanup_errors]
        err = "; ".join(p for p in parts if p)[:2000] or None
        try:
            R.finish_job(factory, job_id, clock.now(), status, stats, err)
        except Exception:
            log.exception("could not finalise job_run %s (status %s)", job_id, status)
            if error is None:
                raise  # nothing else is propagating: this is the error to report
            # otherwise let the original ingestion exception propagate unmasked
    ok = sum(r.ok for r in report.results)
    print(f"{job_name}: {ok}/{len(report.results)} units ok, job_run {job_id}")
    for r in report.failed:
        print(f"  FAILED {r.unit}: {r.error}")
    for c in cleanup_errors:
        print(f"  CLEANUP FAILED {c}")
    return 1 if report.failed or cleanup_errors else 0


def cmd_health(args, clock: Clock) -> int:
    import exchange_calendars as xc

    from mpe.data.ingestion import health_report

    settings, _assets, _engine, factory = _context(clock)
    rep = health_report(
        settings, factory, clock, xc.get_calendar(settings.stocks.calendar, start="2000-01-01")
    )
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    print(f"Data health at {rep['generated_at']}")
    print(f"Markets: {rep['markets']}")
    print(
        f"\n{'provider':<11}{'symbol':<14}{'interval':<9}{'source':<26}{'rows':>7}  {'first':<21}{'last':<21}stale"
    )
    for a in rep["assets"]:
        if a["rows"] == 0:
            continue
        print(f"{a['provider']:<11}{a['symbol']:<14}{a['interval'] or '':<9}{a['source'] or '':<26}{a['rows']:>7}  "
              f"{(a['first'] or ''):<21}{(a['last'] or ''):<21}{'' if a['stale'] is None else a['stale']}")  # fmt: skip
    print("\nQuality events, last 7 days:")
    for k, v in sorted(rep["quality"].items()):
        print(f"  {k}: {v}")
    print("\nRecent jobs:")
    for j in rep["jobs"]:
        print(f"  #{j['id']} {j['job']} {j['scheduled_for']} {j['status']} {j['error'] or ''}")
    return 0


def cmd_db(args, clock: Clock) -> int:
    settings, _a, _e, _f = _context(clock)
    print(f"schema at head: {settings.resolve(settings.database_path)}")
    return 0


def cmd_models(args, clock: Clock) -> int:
    from mpe.models.registry import REGISTRY

    for name in sorted(REGISTRY):
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpe", description="Market Prediction Engine (paper trading only)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--json-logs", action="store_true", help="structured JSON log lines on stderr")
    sub = p.add_subparsers(dest="group", required=True)

    db = sub.add_parser("db")
    db.add_argument("action", choices=["init"])
    db.set_defaults(func=cmd_db)

    ing = sub.add_parser("ingest")
    ing.add_argument("action", choices=["backfill", "update"])
    ing.add_argument("--only", choices=["stocks", "polymarket"])
    ing.add_argument("--symbols", help="comma-separated stock symbols (default: whole watchlist)")
    ing.add_argument("--slot-minutes", type=int, default=30, help="update de-duplication slot")
    ing.add_argument("--raw-dump", action="store_true", help="keep raw Polymarket payloads in data/raw/")
    ing.set_defaults(func=cmd_ingest)

    data = sub.add_parser("data")
    data.add_argument("action", choices=["health"])
    data.add_argument("--json", action="store_true")
    data.set_defaults(func=cmd_health)

    models = sub.add_parser("models")
    models.add_argument("action", choices=["list"])
    models.set_defaults(func=cmd_models)

    from mpe.research.cli import add_parser as add_research

    add_research(sub)
    from mpe.decisions.cli import add_parser as add_decide

    add_decide(sub)
    return p


def main(argv: list[str] | None = None, clock: Clock | None = None) -> int:
    clock = clock or SystemClock()
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    _setup_logging(args.verbose, args.json_logs, run_id=clock.now().strftime("%Y%m%dT%H%M%S"))
    return args.func(args, clock)


if __name__ == "__main__":
    raise SystemExit(main())
