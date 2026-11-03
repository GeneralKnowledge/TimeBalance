"""``mpe research`` commands.

mpe research assets   --domain stocks|polymarket [--json]
mpe research create   --domain stocks|polymarket --mode reconstructed|strict [options] | --config FILE
mpe research list
mpe research run      EXPERIMENT_ID [--models a,b] [--max-forecasts N]
mpe research show     EXPERIMENT_ID [--section summary|models|assets|horizons|calibration|comparisons|exclusions|runs] [--json]
mpe research report   EXPERIMENT_ID
mpe research export   EXPERIMENT_ID [--format csv|json] [--out DIR]

The market-data database is opened read-only. Results go to ``research_database_path``.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from mpe.clock import Clock
from mpe.research.config import (
    BASELINE_MODELS,
    KNOWN_MODELS,
    TIMESTRAL_MODELS,
    ExperimentConfig,
    default_config,
)
from mpe.storage.replay import KnowledgeMode

MODES = {"strict": KnowledgeMode.STRICT, "reconstructed": KnowledgeMode.RECONSTRUCTED}


def add_parser(sub) -> None:
    r = sub.add_parser("research", help="M2 forecasting research laboratory")
    r.add_argument(
        "--market-db", help="market-data SQLite file (default: settings.database_path); opened read-only"
    )
    r.add_argument(
        "--research-db", help="research results SQLite file (default: settings.research_database_path)"
    )
    rs = r.add_subparsers(dest="action", required=True)

    a = rs.add_parser("assets", help="list research assets with data coverage and warnings")
    a.add_argument("--domain", choices=["stocks", "polymarket"], required=True)
    a.add_argument("--json", action="store_true")

    c = rs.add_parser("create", help="create (save) an experiment configuration")
    c.add_argument("--config", type=Path, help="JSON configuration file (all fields explicit)")
    c.add_argument("--domain", choices=["stocks", "polymarket"])
    c.add_argument("--mode", choices=sorted(MODES), help="replay mode; required (no default)")
    c.add_argument("--name")
    c.add_argument("--assets", help="comma-separated symbols / condition ids (default: whole universe)")
    c.add_argument("--start", help="first origin date (UTC, ISO)")
    c.add_argument("--end", help="last origin date (UTC, ISO)")
    c.add_argument("--targets-as-of", help="knowledge time for realised targets (default: now)")
    c.add_argument("--horizons", help="comma-separated steps (default 1,5,20 sessions or 1,6,24 hours)")
    c.add_argument("--models", default="all", help="all | timestral | baselines | comma-separated names")
    c.add_argument("--stride", type=int, help="origin stride in sessions / hours")
    c.add_argument("--context", type=int, help="context length in target points")
    c.add_argument("--min-context", type=int, help="minimum valid context points")
    c.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--print", action="store_true", help="print the configuration without saving it")

    rs.add_parser("list", help="list experiments")

    run = rs.add_parser("run", help="run (or resume) an experiment")
    run.add_argument("experiment_id")
    run.add_argument("--models", help="only these models (comma-separated)")
    run.add_argument(
        "--max-forecasts", type=int, help="stop after this many new forecasts (a resumable batch)"
    )
    run.add_argument("--allow-code-change", action="store_true", help="silence the code-version warning")

    sh = rs.add_parser("show", help="inspect results")
    sh.add_argument("experiment_id")
    sh.add_argument("--section", default="summary",
                    choices=["summary", "models", "assets", "horizons", "calibration", "comparisons", "exclusions",
                             "runs", "config"])  # fmt: skip
    sh.add_argument("--json", action="store_true")

    rp = rs.add_parser("report", help="write reports/experiments/<id>/<tag>/ (never overwrites)")
    rp.add_argument("experiment_id")

    ex = rs.add_parser("export", help="export raw forecasts, targets and metrics")
    ex.add_argument("experiment_id")
    ex.add_argument("--format", choices=["csv", "json"], default="csv")
    ex.add_argument("--out", type=Path, help="directory (default: reports/experiments/<id>/export-<format>)")
    r.set_defaults(func=cmd_research)


def _ctx(args):
    from sqlalchemy.orm import sessionmaker

    from mpe.config import load_settings
    from mpe.research.store import ResearchStore, make_readonly_market_engine, make_research_engine

    settings = load_settings()
    market_path = Path(args.market_db) if args.market_db else settings.resolve(settings.database_path)
    research_path = (
        Path(args.research_db) if args.research_db else settings.resolve(settings.research_database_path)
    )
    market = sessionmaker(bind=make_readonly_market_engine(market_path), expire_on_commit=False, future=True)
    return settings, market, ResearchStore(make_research_engine(research_path))


def _models(spec: str) -> list[str]:
    if spec == "all":
        return list(KNOWN_MODELS)
    if spec == "timestral":
        return list(TIMESTRAL_MODELS)
    if spec == "baselines":
        return list(BASELINE_MODELS)
    names = [m.strip() for m in spec.split(",") if m.strip()]
    bad = [m for m in names if m not in KNOWN_MODELS]
    if bad:
        raise SystemExit(f"unknown models {bad}; known: {list(KNOWN_MODELS)}")
    return names


def _dt(text: str) -> datetime:
    d = datetime.fromisoformat(text)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def cmd_research(args, clock: Clock) -> int:
    settings, market, store = _ctx(args)
    return {"assets": _assets, "create": _create, "list": _list, "run": _run, "show": _show,
            "report": _report, "export": _export}[args.action](args, clock, settings, market, store)  # fmt: skip


def _assets(args, clock, settings, market, store) -> int:
    from mpe.research.data import describe_assets

    with market() as s:
        rows = describe_assets(s, args.domain, settings.stocks.calendar)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{'asset':<16}{'source':<25}{'int':<5}{'first':<22}{'last':<22}{'usable':>8}  warnings")
    for r in rows:
        key = r["key"] if len(r["key"]) <= 15 else r["key"][:12] + "…"
        print(f"{key:<16}{r['source']:<25}{r['interval']:<5}{r['first'] or '':<22}{r['last'] or '':<22}"
              f"{r.get('usable_observations', 0):>8}  {'; '.join(r['warnings'])}")  # fmt: skip
        if args.domain == "polymarket":
            print(f"{'':<16}{r.get('status', '')}: {r.get('label', '')[:90]}")
    retrieved = sorted({r["retrieved_last"] for r in rows if r.get("retrieved_last")})
    if retrieved:
        print(f"\nAll rows retrieved between {min(r['retrieved_first'] for r in rows if r.get('retrieved_first'))} and "
              f"{retrieved[-1]}: strict replay sees nothing before the first retrieval.")  # fmt: skip
    return 0


def _create(args, clock, settings, market, store) -> int:
    from mpe.research.data import default_polymarket_universe, default_stock_universe
    from mpe.research.store import ExperimentExists

    if args.config:
        cfg = ExperimentConfig.model_validate_json(args.config.read_text())
    else:
        if not args.domain or not args.mode:
            raise SystemExit("--domain and --mode are required (or --config)")
        now = clock.now().replace(microsecond=0)
        with market() as s:
            if args.assets:
                assets = [a.strip() for a in args.assets.split(",") if a.strip()]
            else:
                assets = (
                    default_stock_universe(s) if args.domain == "stocks" else default_polymarket_universe(s)
                )
        excluded = []
        if args.domain == "stocks" and not args.assets:
            fx = [a for a in assets if a.endswith("=X")]
            assets = [a for a in assets if a not in fx]
            excluded = [{"asset": a, "reason": "FX: not on the XNYS calendar; M2 stock experiments use XNYS sessions"}
                        for a in fx]  # fmt: skip
        tao = _dt(args.targets_as_of) if args.targets_as_of else now
        if args.domain == "stocks":
            start = _dt(args.start) if args.start else datetime(2016, 1, 1, tzinfo=UTC)
            end = _dt(args.end) if args.end else tao - timedelta(days=35)
        else:
            start = _dt(args.start) if args.start else datetime(2025, 6, 1, tzinfo=UTC)
            end = _dt(args.end) if args.end else tao - timedelta(days=2)
        kw: dict = {"device": args.device, "seed": args.seed, "excluded_assets": excluded}
        if args.horizons:
            kw["horizons"] = [int(h) for h in args.horizons.split(",")]
        if args.stride:
            kw["origin_stride"] = args.stride
        if args.context:
            kw["context_length"] = args.context
            if not args.min_context:
                kw["min_context_observations"] = max(
                    2, int(args.context * (0.9375 if args.domain == "stocks" else 0.5))
                )
        if args.min_context:
            kw["min_context_observations"] = args.min_context
        models = _models(args.models)
        ref = "zero" if args.domain == "stocks" else "persistence"
        if ref not in models:
            models.append(ref)
        name = args.name or f"{args.domain} {args.mode} {start:%Y-%m-%d}..{end:%Y-%m-%d}"
        cfg = default_config(args.domain, name=name, knowledge_mode=MODES[args.mode], assets=assets,
                             settings=settings, origin_start=start, origin_end=end, targets_as_of=tao,
                             models=models, **kw)  # fmt: skip
    if args.print:
        print(cfg.to_json())
        return 0
    try:
        eid = store.create(cfg, clock.now())
    except ExperimentExists as e:
        print(f"experiment {e} already exists with this exact configuration; run or inspect it")
        return 0
    print(eid)
    if cfg.knowledge_mode == KnowledgeMode.RECONSTRUCTED:
        print(
            "  reconstructed research: results are not what the system genuinely knew at the time",
            file=sys.stderr,
        )
    return 0


def _list(args, clock, settings, market, store) -> int:
    for r in store.list():
        print(
            f"{r['experiment_id']:<26}{r['status']:<12}{r['knowledge_mode']:<24}{r['created_at']:<22}{r['name']}"
        )
    return 0


def _progress(model: str, done: int, total: int, elapsed: float) -> None:
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else float("nan")
    print(f"  {model}: {done}/{total} forecasts, {rate:.1f}/s, ETA {eta:.0f}s", file=sys.stderr, flush=True)


def _run(args, clock, settings, market, store) -> int:
    from mpe.research.runner import ExperimentRunner

    runner = ExperimentRunner(market, store, clock, progress=_progress)
    models = [m.strip() for m in args.models.split(",")] if args.models else None
    try:
        res = runner.run(args.experiment_id, models=models, max_forecasts=args.max_forecasts,
                         allow_code_change=args.allow_code_change)  # fmt: skip
    except KeyboardInterrupt:
        print(
            "interrupted; completed forecasts are saved. Re-run the same command to resume.", file=sys.stderr
        )
        return 130
    for m, r in res["models"].items():
        print(f"{m:<16}{r['status']:<11}new {r['new']:>7}  failed {r['failed']:>5}  {r.get('device') or ''}"
              f"{'  ERROR ' + r['error'] if r.get('error') else ''}")  # fmt: skip
    print(f"experiment {args.experiment_id}: {res['status']}")
    return 0 if res["status"] == "completed" else 2


def _show(args, clock, settings, market, store) -> int:
    from mpe.research.analysis import full_analysis

    exp = store.get(args.experiment_id)
    if args.section == "config":
        print(exp.config.to_json())
        return 0
    if args.section == "runs":
        df = pd.DataFrame(store.model_runs(args.experiment_id))
        print(df.to_json(orient="records", indent=1) if args.json else df.to_string(index=False))
        return 0
    res = full_analysis(store, args.experiment_id)
    sc = res["scored"]
    if args.section == "exclusions":
        payload = {"preparation": exp.prepare, "exclusions": sc.exclusions}
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if args.section == "summary":
        lb = res["leaderboard"]
        info = {"experiment_id": exp.experiment_id, "name": exp.config.name, "status": exp.status,
                "knowledge_mode": exp.config.knowledge_mode.value, "domain": exp.config.domain,
                "models": exp.config.model_names, "model_versions": exp.model_versions,
                "scored_cases": len(sc.rows), "exclusions": sc.exclusions}  # fmt: skip
        if args.json:
            print(
                json.dumps(
                    {**info, "leaderboard": json.loads(lb.to_json(orient="records"))}, indent=2, default=str
                )
            )
            return 0
        for k, v in info.items():
            if k != "exclusions":
                print(f"{k}: {v}")
        if exp.config.knowledge_mode == KnowledgeMode.RECONSTRUCTED:
            print("RECONSTRUCTED RESEARCH: backfilled data under documented availability assumptions")
        cols = [c for c in ("horizon", "model", "n", "mae", "rmse", "crps", "cov_0.9", "dir_acc", "rel_mae", "rel_crps")
                if c in lb.columns]  # fmt: skip
        print(lb[cols].to_string(index=False) if not lb.empty else "no scored cases")
        return 0
    table = {
        "models": res["leaderboard"],
        "horizons": res["leaderboard"].groupby("model", sort=False).agg(n=("n", "sum")).reset_index()
        if res["leaderboard"].empty
        else res["leaderboard"],
        "assets": res["per_asset"],
        "calibration": res["calibration"],
        "comparisons": res["comparisons"],
    }[args.section]
    if args.section == "horizons" and not table.empty:
        table = table.sort_values(["horizon", "crps"])
    print(table.to_json(orient="records", indent=1) if args.json else
          (table.to_string(index=False) if not table.empty else "no rows"))  # fmt: skip
    return 0


def _report(args, clock, settings, market, store) -> int:
    from mpe.research.report import write_report

    out = write_report(store, args.experiment_id)
    print(out)
    return 0


def _export(args, clock, settings, market, store) -> int:
    from mpe.research.report import REPORTS, export

    out = args.out or (REPORTS / args.experiment_id / f"export-{args.format}")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty; choose --out (exports never overwrite)")
    for p in export(store, args.experiment_id, out, args.format):
        print(p)
    return 0
