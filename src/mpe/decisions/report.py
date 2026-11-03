"""Markdown + SVG report for a decision-model evaluation (never overwrites an earlier report)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mpe.research.report import _fmt, md_table, svg_lines

REPORTS = Path(__file__).resolve().parents[3] / "reports" / "decisions"


def _json_default(x):
    if isinstance(x, pd.DataFrame):
        return x.to_dict("records")
    return str(x)


def write_report(run: dict, res: dict, eval_id: str, cfg: dict, root: Path | None = None) -> Path:
    out = (root or REPORTS) / run["run_id"] / eval_id
    if out.exists():
        raise FileExistsError(f"{out} exists; evaluations are never overwritten")
    out.mkdir(parents=True)
    summary = {k: v for k, v in res.items() if k != "frame"}
    (out / "summary.json").write_text(json.dumps(summary, default=_json_default, indent=1))
    (out / "config.json").write_text(json.dumps({"run": {k: run[k] for k in run if k != "questions_json"},
                                                 "evaluation": cfg}, indent=1, default=str))  # fmt: skip
    res["frame"].drop(columns=[c for c in res["frame"].columns if c.startswith("dirp_")]).to_csv(
        out / "points.csv", index=False)  # fmt: skip
    rel = res["reliability"]
    x = [f"{(i + 0.5) / 10:.2f}" for i in range(10)]
    (out / "reliability.svg").write_text(svg_lines(
        "Reliability: observed YES rate by forecast bin", [float(v) for v in x],
        {k: v["observed_yes"].tolist() for k, v in rel.items()}, "observed YES rate", diagonal=True,
        categorical=False))  # fmt: skip
    (out / "report.md").write_text(render(run, res, cfg))
    return out


def render(run: dict, res: dict, cfg: dict) -> str:
    bench = json.loads(run["benchmark_json"] or "{}")
    hw = json.loads(run["hardware_json"] or "{}")
    p = res["probability"]
    lines = [
        f"# Decision-model evaluation: {run['model_name']}",
        "",
        (
            "**Reconstructed research.** Price histories were retrieved after the markets resolved; "
            "`available_at` follows the provider's backfill rule. This is not a genuine point-in-time "
            "backtest. The sample was chosen by lifetime volume, which is only known afterwards."
        ),
        "",
        (
            f"- Run `{run['run_id']}`; checkpoint `{run['checkpoint']}` at revision `{run['model_version']}`; "
            f"laya {run['library_version']}"
        ),
        (
            f"- Questions `{run['question_version']}` (hash `{run['question_hash']}`), state template "
            f"`{run['state_template']}`, snapshot schema `{run['snapshot_schema']}`"
        ),
        (
            f"- {res['points']} decision points on {res['markets']} resolved markets, decision times "
            f"{res['period'][0]} to {res['period'][1]}; {res['errors']} inference errors; "
            f"{res['abstained']} points where Laya said there was not enough information"
        ),
        "",
        "## Hardware and inference",
        "",
        "| measure | value |\n|---|---|",
        *[f"| {k} | {_fmt(v)} |" for k, v in {**hw, **bench}.items()],
        "",
        "## Probability that the market resolves YES",
        "",
        (
            "All forecasters on identical points. `market` is the last YES price at the decision time. "
            "`*_recal` and `market_plus_laya` are walk-forward logistic fits on earlier-resolved markets. "
            "`brier_minus_market` < 0 means better than the market; the 95% interval resamples whole markets."
        ),
        "",
        md_table(
            p,
            [
                ("forecaster", "forecaster"),
                ("n", "n"),
                ("markets", "markets"),
                ("brier", "Brier"),
                ("log_loss", "log loss"),
                ("ece", "ECE"),
                ("brier_minus_market", "Δ Brier vs market"),
                ("ci_low", "CI low"),
                ("ci_high", "CI high"),
            ],
        ),
        (
            f"Correlation of Laya's raw P(YES) with the market price: {_fmt(res['laya_vs_market_corr'])}. "
            f"Histogram of raw P(YES) in tenths: {res['laya_raw_distribution']}."
        ),
        "",
        "### Contested markets only (market price between 5% and 95%)",
        "",
        md_table(
            res["probability_contested"],
            [
                ("forecaster", "forecaster"),
                ("n", "n"),
                ("brier", "Brier"),
                ("log_loss", "log loss"),
                ("brier_minus_market", "Δ Brier vs market"),
                ("ci_low", "CI low"),
                ("ci_high", "CI high"),
            ],
        ),
        "### Brier by lead time",
        "",
        _df(res["by_lead"]),
        "### Brier by category",
        "",
        _df(res["by_category"]),
        "### Reliability (raw Laya vs market)",
        "",
        "![reliability](reliability.svg)",
        "",
        "## Direction of the YES price",
        "",
        "`unchanged` means within 1 point. Baselines see the same snapshot.",
        "",
        _df(res["direction"]),
        "## Paper-trading simulation (hold to resolution)",
        "",
        (
            f"Costs: half-spread {cfg['half_spread']}, slippage {cfg['slippage']}, the market's fee rate "
            f"(default {cfg['default_fee_rate']}), stake ${cfg['stake_usd']} per trade, one trade per market. "
            "Spread and depth are assumed, not observed. A high win rate is not evidence of profit."
        ),
        "",
        "| signal | min edge | trades | net P&L $ | return on turnover | win rate | avg edge | max drawdown $ |",
        "|---|---|---|---|---|---|---|---|",
        *[
            f"| {t['signal']} | {t['min_edge']} | {t['trades']} | {_fmt(t.get('net_pnl'))} | "
            f"{_fmt(t.get('return_on_turnover'))} | {_fmt(t.get('win_rate'))} | {_fmt(t.get('avg_edge'))} | "
            f"{_fmt(t.get('max_drawdown'))} |"
            for t in res["trading"]
        ],
        "",
        "## Disagreement with the market",
        "",
        (
            "`corr` is the correlation between (Laya − market) and (outcome − market). Positive means Laya "
            "leans the right way when it disagrees."
        ),
        "",
        *[
            f"- {name}: n={d.get('n')}, corr={_fmt(d.get('corr_disagreement_vs_market_error'))} "
            f"(95% CI {d.get('corr_ci')}); quantitative baseline corr="
            f"{_fmt(d.get('corr_quant_baseline_vs_market_error'))}; Laya vs baseline disagreement corr="
            f"{_fmt(d.get('corr_laya_vs_quant_disagreement'))}"
            for name, d in (("raw", res["disagreement_raw"]), ("recalibrated", res["disagreement_recal"]))
        ],
        "",
        _df(pd.DataFrame(res["disagreement_raw"].get("buckets", []))),
        "## Regime and opportunity answers",
        "",
        _df(res["regime"]),
        f"Opportunity answers: {res['opportunity_counts']}",
        "",
    ]
    return "\n".join(lines)


def _df(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_No rows._\n"
    return md_table(df, [(c, c) for c in df.columns])
