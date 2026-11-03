"""``mpe decide``: the decision-model experiment, independent of the M2 research pipeline.

mpe decide fetch     [--end-min 2026-05-01] [--end-max 2026-10-31] [--max-markets 300] [--min-volume 50000]
mpe decide snapshots [--leads 168,48,24,6]
mpe decide run       [--checkpoint typed-decisions] [--device auto|cpu|cuda] [--max-snapshots N] [--resume RUN]
mpe decide evaluate  RUN_ID [--fee-rate R] [--half-spread S]
mpe decide runs

Results live in ``data/decisions.sqlite3`` (append-only) and ``reports/decisions/<run>/<eval>/``.
Nothing here places orders or needs credentials.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from mpe.clock import Clock

DEFAULT_DB = "data/decisions.sqlite3"


def add_parser(sub) -> None:
    d = sub.add_parser("decide", help="decision-model (Laya) experiment on resolved Polymarket markets")
    d.add_argument("--db", default=DEFAULT_DB)
    s = d.add_subparsers(dest="decide_cmd", required=True)
    f = s.add_parser("fetch")
    f.add_argument("--end-min", default="2026-05-01")
    f.add_argument("--end-max", default="2026-10-31")
    f.add_argument("--max-markets", type=int, default=300)
    f.add_argument("--min-volume", type=float, default=50_000)
    f.add_argument("--include-neg-risk", action="store_true")
    sn = s.add_parser("snapshots")
    sn.add_argument("--leads", default="168,48,24,6")
    r = s.add_parser("run")
    r.add_argument("--checkpoint", default="typed-decisions")
    r.add_argument("--revision")
    r.add_argument("--device", default="auto")
    r.add_argument("--binary-as", default="choice", choices=["choice", "noul"])
    r.add_argument("--batch-size", type=int, default=8)
    r.add_argument("--max-snapshots", type=int)
    r.add_argument("--resume")
    e = s.add_parser("evaluate")
    e.add_argument("run_id")
    e.add_argument("--fee-rate", type=float, help="override every market's fee rate (sensitivity)")
    e.add_argument("--half-spread", type=float, default=0.01)
    e.add_argument("--slippage", type=float, default=0.005)
    s.add_parser("runs")
    d.set_defaults(func=cmd_decide)


def cmd_decide(args, clock: Clock) -> int:
    from mpe.config import ROOT
    from mpe.decisions.store import DecisionStore

    store = DecisionStore(ROOT / args.db if not args.db.startswith("/") else args.db)
    try:
        return {"fetch": _fetch, "snapshots": _snapshots, "run": _run, "evaluate": _evaluate,
                "runs": _runs}[args.decide_cmd](args, clock, store)  # fmt: skip
    finally:
        store.close()


def _day(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _fetch(args, clock, store) -> int:
    from mpe.config import load_settings
    from mpe.data.providers.polymarket import PolymarketProvider
    from mpe.decisions.dataset import fetch_resolved_markets

    prov = PolymarketProvider(load_settings(), clock)
    try:
        stats = fetch_resolved_markets(prov, store, end_min=_day(args.end_min), end_max=_day(args.end_max),
                                       max_markets=args.max_markets, min_volume=args.min_volume,
                                       include_neg_risk=args.include_neg_risk)  # fmt: skip
    finally:
        prov.close()
    print(json.dumps(stats, indent=1))
    return 0


def _snapshots(args, clock, store) -> int:
    from mpe.decisions.dataset import make_snapshots

    print(json.dumps(make_snapshots(store, tuple(int(x) for x in args.leads.split(","))), indent=1))
    return 0


def _run(args, clock, store) -> int:
    from mpe.decisions.laya_model import LayaDecisionModel
    from mpe.decisions.runner import run_decisions

    model = LayaDecisionModel(args.checkpoint, revision=args.revision, binary_as=args.binary_as,
                              batch_size=args.batch_size)  # fmt: skip
    run_id = run_decisions(store, model, clock, device=args.device, max_snapshots=args.max_snapshots,
                           resume_run=args.resume)  # fmt: skip
    print(run_id)
    print(store.run(run_id)["benchmark_json"])
    return 0


def _evaluate(args, clock, store) -> int:
    from mpe.decisions.dataset import history_points
    from mpe.decisions.evaluate import EvalConfig, evaluate
    from mpe.decisions.report import write_report
    from mpe.decisions.snapshot import iso

    run = store.run(args.run_id)
    cfg = EvalConfig(half_spread=args.half_spread, slippage=args.slippage, fee_rate_override=args.fee_rate)
    outputs = store.outputs(args.run_id)
    markets = {m["condition_id"]: m for m in store.markets()}
    hist = {cid: history_points(store, cid) for cid in markets}
    res = evaluate(outputs, markets, hist, cfg)
    now = clock.now()
    cfg_d = asdict(cfg)
    eval_id = (
        f"eval-{now:%Y%m%dT%H%M%S}-"
        + hashlib.sha256(json.dumps(cfg_d, sort_keys=True).encode()).hexdigest()[:6]
    )
    out = write_report(run, res, eval_id, cfg_d)
    store.insert_evaluation({"eval_id": eval_id, "run_id": args.run_id, "created_at": iso(now),
                             "config_json": json.dumps(cfg_d),
                             "results_json": (out / "summary.json").read_text(), "report_dir": str(out)})  # fmt: skip
    print(out / "report.md")
    return 0


def _runs(args, clock, store) -> int:
    for r in store.runs():
        print(json.dumps(r))
    return 0
