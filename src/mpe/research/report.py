"""Reports and exports for a stored experiment.

``write_report`` writes ``reports/experiments/<experiment_id>/<tag>/`` where ``tag`` is derived from
the content of the results, so an identical report is never written twice and an earlier report
is never overwritten (new results get a new tag next to the old one). Figures are plain SVG
written here, so reporting adds no plotting dependency.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from mpe.config import ROOT
from mpe.research.analysis import full_analysis
from mpe.research.config import TIMESTRAL_MODELS
from mpe.research.store import ResearchStore, forecasts, origins, targets, unpack

REPORTS = ROOT / "reports" / "experiments"
CONCLUSIONS = ("better", "worse", "no demonstrated difference", "insufficient data")


def _fmt(x, digits: int = 4) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    if isinstance(x, float):
        if x != 0 and (abs(x) < 1e-3 or abs(x) >= 1e5):
            return f"{x:.{digits - 1}e}"
        return f"{x:.{digits}g}" if abs(x) >= 1 else f"{x:.{digits}f}"
    return str(x)


def _pct(x) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:+.1f}%"


def md_table(df: pd.DataFrame, cols: list[tuple[str, str]], pct: tuple[str, ...] = ()) -> str:
    if df.empty:
        return "_No rows._\n"
    head = "| " + " | ".join(h for _, h in cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for _, r in df.iterrows():
        body += "| " + " | ".join(_pct(r[c]) if c in pct else _fmt(r[c]) for c, _ in cols) + " |\n"
    return head + body


# ------------------------------------------------------------------ SVG
PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4b5563", "#ca8a04", "#db2777"]


def svg_lines(title: str, x: list, series: dict[str, list[float]], y_label: str, diagonal: bool = False,
              categorical: bool = True) -> str:  # fmt: skip
    W, H, L, R, T, B = 760, 380, 70, 190, 40, 60
    vals = [v for s in series.values() for v in s if v is not None and not math.isnan(v)]
    if diagonal:
        vals += [float(v) for v in x]
    if not vals:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="80"><text x="10" y="40">{html.escape(title)}: no data</text></svg>'
    lo, hi = min(vals), max(vals)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.05
    lo, hi = lo - pad, hi + pad
    n = len(x)
    xs = [float(v) for v in x] if not categorical else list(range(n))
    x0, x1 = (min(xs), max(xs)) if n > 1 else (0, 1)
    if x1 == x0:
        x1 = x0 + 1

    def px(v):
        return L + (v - x0) / (x1 - x0) * (W - L - R)

    def py(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="11">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="{W / 2}" y="20" text-anchor="middle" font-size="14">{html.escape(title)}</text>']  # fmt: skip
    for k in range(6):
        v = lo + (hi - lo) * k / 5
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="#e5e7eb"/>')
        out.append(f'<text x="{L - 6}" y="{py(v) + 4:.1f}" text-anchor="end">{v:.3g}</text>')
    step = max(1, n // 12)
    for i in range(0, n, step):
        out.append(
            f'<text x="{px(xs[i]):.1f}" y="{H - B + 16}" text-anchor="middle">{html.escape(str(x[i]))}</text>'
        )
    out.append(f'<text x="16" y="{(H - B + T) / 2}" transform="rotate(-90 16 {(H - B + T) / 2})" '
               f'text-anchor="middle">{html.escape(y_label)}</text>')  # fmt: skip
    if diagonal:
        out.append(f'<line x1="{px(x0):.1f}" y1="{py(x0):.1f}" x2="{px(x1):.1f}" y2="{py(x1):.1f}" '
                   'stroke="#9ca3af" stroke-dasharray="4 3"/>')  # fmt: skip
    if not diagonal and lo < 0 < hi:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{py(0):.1f}" y2="{py(0):.1f}" stroke="#6b7280"/>')
    for j, (name, s) in enumerate(series.items()):
        col = PALETTE[j % len(PALETTE)]
        pts = [(px(xs[i]), py(v)) for i, v in enumerate(s) if v is not None and not math.isnan(v)]
        if pts:
            out.append('<polyline fill="none" stroke="{}" stroke-width="1.6" points="{}"/>'.format(
                col, " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)))  # fmt: skip
            out += [f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2" fill="{col}"/>' for a, b in pts]
        ly = T + 14 * j
        out.append(f'<rect x="{W - R + 12}" y="{ly}" width="10" height="10" fill="{col}"/>')
        out.append(f'<text x="{W - R + 26}" y="{ly + 9}">{html.escape(name)}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ------------------------------------------------------------------ report
def _summary_payload(store: ResearchStore, eid: str, res: dict) -> dict:
    exp = store.get(eid)
    sc = res["scored"]
    return {
        "experiment_id": eid,
        "name": exp.config.name,
        "status": exp.status,
        "created_at": exp.created_at,
        "code_version_at_creation": exp.code_version,
        "knowledge_mode": exp.config.knowledge_mode.value,
        "label": _mode_label(exp.config.knowledge_mode.value),
        "model_versions": exp.model_versions,
        "config": json.loads(exp.config.to_json()),
        "preparation": exp.prepare,
        "exclusions": sc.exclusions,
        "n_scored_rows": len(sc.rows),
        "model_runs": store.model_runs(eid),
        "leaderboard": _records(res["leaderboard"]),
        "comparisons": _records(res["comparisons"]),
        "per_asset": _records(res["per_asset"]),
        "calibration": _records(res["calibration"]),
        "over_time": _records(res["over_time"]),
        "resolution": res["resolution"],
    }


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", double_precision=10, date_format="iso"))


def _mode_label(mode: str) -> str:
    if mode == "reconstructed_history":
        return ("RECONSTRUCTED RESEARCH: inputs are backfilled data replayed under documented availability "
                "assumptions. This is not what the system genuinely knew at the time.")  # fmt: skip
    return "STRICT POINT-IN-TIME: only data the system had actually retrieved by each cutoff."


def write_report(store: ResearchStore, eid: str, root: Path = REPORTS) -> Path:
    res = full_analysis(store, eid)
    payload = _summary_payload(store, eid, res)
    blob = json.dumps(payload, sort_keys=True, default=str)
    tag = (
        "report-"
        + hashlib.sha256(
            json.dumps(
                {k: v for k, v in payload.items() if k != "model_runs"}, sort_keys=True, default=str
            ).encode()
        ).hexdigest()[:10]
    )
    out = root / eid / tag
    if out.exists() and (out / "report.md").exists():
        return out  # identical results already reported; never overwritten
    tmp = root / eid / (tag + ".partial")
    tmp.mkdir(parents=True, exist_ok=True)
    exp = store.get(eid)
    (tmp / "config.json").write_text(exp.config.to_json() + "\n")
    (tmp / "summary.json").write_text(json.dumps(json.loads(blob), indent=2, sort_keys=True) + "\n")
    for k in ("leaderboard", "comparisons", "per_asset", "calibration", "over_time"):
        df = res[k]
        (tmp / f"{k}.csv").write_text(df.to_csv(index=False) if df is not None and not df.empty else "")
    pd.DataFrame(store.model_runs(eid)).to_csv(tmp / "model_runs.csv", index=False)
    figs = _figures(res, exp.config, tmp)
    (tmp / "report.md").write_text(render_markdown(store, eid, res, figs))
    tmp.rename(out)
    return out


def _figures(res: dict, cfg, out: Path) -> list[str]:
    names = []
    cal = res["calibration"]
    ot = res["over_time"]
    unit = "sessions" if cfg.domain == "stocks" else "hours"
    for h in cfg.horizons:
        c = cal[(cal["horizon"] == h) & (cal["kind"] == "quantile")] if not cal.empty else cal
        if not c.empty:
            x = sorted(c["nominal"].unique())
            series = {m: [float(c[(c["model"] == m) & (c["nominal"] == v)]["empirical"].iloc[0]) for v in x]
                      for m in cfg.model_names if (c["model"] == m).any()}  # fmt: skip
            f = f"calibration_h{h}.svg"
            (out / f).write_text(svg_lines(f"Quantile calibration, h = {h} {unit}: share of outcomes <= quantile",
                                           x, series, "empirical frequency", diagonal=True, categorical=False))  # fmt: skip
            names.append(f)
        o = ot[ot["horizon"] == h] if not ot.empty else ot
        if not o.empty:
            periods = sorted(o["period"].unique())
            series = {}
            for m in cfg.model_names:
                if m == cfg.reference_baseline:
                    continue
                om = o[o["model"] == m].set_index("period")["rel_crps"]
                series[m] = [float(om.get(p, math.nan)) for p in periods]
            f = f"over_time_h{h}.svg"
            (out / f).write_text(svg_lines(f"CRPS improvement over {cfg.reference_baseline} by period, h = {h} {unit}",
                                           periods, series, f"1 - CRPS / CRPS({cfg.reference_baseline})"))  # fmt: skip
            names.append(f)
    return names


def render_markdown(store: ResearchStore, eid: str, res: dict, figs: list[str]) -> str:
    exp = store.get(eid)
    cfg = exp.config
    sc = res["scored"]
    lb, cmp_, pa, cal, ot = (
        res["leaderboard"],
        res["comparisons"],
        res["per_asset"],
        res["calibration"],
        res["over_time"],
    )
    unit = "trading sessions" if cfg.domain == "stocks" else "hours"
    ref = cfg.reference_baseline
    s = [f"# Experiment `{eid}`: {cfg.name}\n",
         f"> **{_mode_label(cfg.knowledge_mode.value)}**\n",
         (f"Status: **{exp.status}**. Created {exp.created_at} at code version `{exp.code_version}`. "
          "This is forecasting research. It is not a trading signal and says nothing about profitability.\n")]  # fmt: skip
    s.append("## Configuration\n")
    s.append("| field | value |\n|---|---|\n")
    target = ("daily log return of `close`" if cfg.target == "log_return"
              else f"logit of the YES token price (eps {cfg.logit_eps}); probabilities via inverse logit")  # fmt: skip
    rows = [
        ("domain", cfg.domain), ("knowledge mode", cfg.knowledge_mode.value), ("source / interval", f"{cfg.source} / {cfg.interval}"),
        ("calendar", cfg.calendar or "UTC hours"), ("target", target), ("price field", cfg.price_field),
        ("assets requested", len(cfg.assets)), ("origins", f"{cfg.origin_start:%Y-%m-%d %H:%M} to {cfg.origin_end:%Y-%m-%d %H:%M} UTC, every {cfg.origin_stride} {'sessions' if cfg.domain == 'stocks' else 'hours'}"),
        ("cutoff", f"origin timestamp + {cfg.cutoff_delay_seconds} s; extra replay latency {cfg.extra_latency_seconds} s"),
        ("targets read as of", f"{cfg.targets_as_of:%Y-%m-%d %H:%M} UTC"),
        ("context", f"{cfg.context_length} points (min {cfg.min_context_observations} valid, max {cfg.max_missing_context_fraction:.0%} missing)"),
        ("horizons", ", ".join(f"{h}" for h in cfg.horizons) + f" {unit}"), ("quantile levels", f"{len(cfg.quantile_levels)} in [{min(cfg.quantile_levels)}, {max(cfg.quantile_levels)}]"),
        ("reference baseline", ref), ("seed / device requested", f"{cfg.seed} / {cfg.device}"),
        ("availability rule", cfg.availability.get("rule", "")),
        ("model versions", ", ".join(f"{k}={v[:12]}" for k, v in sorted(exp.model_versions.items()))),
    ]  # fmt: skip
    s += [f"| {a} | {html.escape(str(b))} |\n" for a, b in rows]
    s.append("\n## Data and exclusions\n")
    prep = exp.prepare or {}
    assets = prep.get("assets", {})
    n_ok = sum(a.get("ok_origins", 0) for a in assets.values())
    s.append(f"- Assets prepared: {len(assets)}; usable origins: {n_ok:,}; scored cases in the common sample: "
             f"{len(sc.rows) // max(1, len(cfg.models)):,} per model.\n")  # fmt: skip
    for e in sc.exclusions.get("excluded_assets", []):
        s.append(f"- Asset excluded: `{e['asset']}`: {e['reason']}.\n")
    for k, v in sorted(sc.exclusions["skipped_grid_origins"].items()):
        if v:
            s.append(f"- Grid origins skipped ({k}): {v:,}.\n")
    for k, v in sorted(sc.exclusions["origins"].items()):
        s.append(f"- Origins excluded ({k}): {v:,}.\n")
    for k, v in sorted(sc.exclusions["targets"].items()):
        s.append(f"- Origin-horizon cases without a realised target ({k}): {v:,}.\n")
    for m, v in sorted(sc.exclusions["forecast_failures"].items()):
        s.append(f"- Forecast failures for {m}: {v:,} (examples in summary.json).\n")
    if sc.exclusions.get("origins_without_all_models"):
        s.append(f"- Origins left out of the common sample because some model has no valid forecast: "
                 f"{sc.exclusions['origins_without_all_models']:,}.\n")  # fmt: skip
    pending = {m: v for m, v in sc.exclusions.get("not_yet_forecast", {}).items() if v}
    if pending:
        s.append(f"- **Not yet forecast** (experiment incomplete): {pending}.\n")
    if sc.rows.empty:
        s.append("\n**No scored cases.** Nothing below can be interpreted.\n")
        return "".join(s)

    s.append(f"\n## Leaderboard\n\nPooled over all scored cases (every case equal weight); `macro MAE` is the mean "
             f"of per-asset MAEs. Relative columns are `1 - metric / metric({ref})`: positive is better than "
             f"`{ref}`. CRPS_q is the quantile CRPS over levels [{min(cfg.quantile_levels)}, {max(cfg.quantile_levels)}] "
             "(no tail extrapolation). Directional accuracy excludes zero changes.\n")  # fmt: skip
    cols = [("model", "model"), ("n", "n"), ("n_assets", "assets"), ("mae", "MAE"), ("rmse", "RMSE"),
            ("mean_error", "mean err"), ("pinball", "pinball"), ("crps", "CRPS_q"), ("cov_0.9", "cov 90%"),
            ("width_0.9", "width 90%"), ("dir_acc", "dir acc"), ("rel_mae", "ΔMAE"), ("rel_crps", "ΔCRPS"),
            ("macro_mae", "macro MAE")]  # fmt: skip
    if cfg.domain == "polymarket":
        cols[3:3] = [("mae_p", "MAE (prob)"), ("rmse_p", "RMSE (prob)")]
    for h in cfg.horizons:
        s.append(f"\n### h = {h} {unit}\n\n")
        s.append(md_table(lb[lb["horizon"] == h], cols, pct=("rel_mae", "rel_crps")))
    if not cmp_.empty:
        s.append(f"\n## Paired comparisons\n\nMean loss difference (model − comparator) over identical cases; "
                 "negative is better. 95% CI from a moving-block bootstrap over origin dates "
                 f"({cfg.bootstrap_samples} resamples, block ≥ horizon/stride). `insufficient data` when there are "
                 f"fewer than {cfg.min_paired_dates} origin dates or fewer than 10 blocks. "
                 f"{len(cmp_)} comparisons are shown, so about {len(cmp_) * 0.05:.0f} could exclude zero by chance alone.\n\n")  # fmt: skip
        c2 = cmp_.copy()
        c2["ci"] = [
            f"[{_fmt(a)}, {_fmt(b)}]" for a, b in zip(c2.get("ci_low"), c2.get("ci_high"), strict=True)
        ]
        s.append(md_table(c2, [("horizon", "h"), ("loss", "loss"), ("model", "model"), ("reference", "vs"),
                               ("against", "comparator"), ("mean_diff", "mean diff"), ("ci", "95% CI"),
                               ("rel_improvement", "rel. improvement"), ("n_pairs", "pairs"), ("n_assets", "assets"),
                               ("n_dates", "dates"), ("conclusion", "conclusion")], pct=("rel_improvement",)))  # fmt: skip
    if not pa.empty:
        s.append(
            f"\n## Per-asset results (CRPS_q vs {ref})\n\nCounts of assets by conclusion, then the detail.\n\n"
        )
        p = pa[pa["loss"] == "crps"]
        counts = p.groupby(["horizon", "model", "conclusion"]).size().unstack(fill_value=0)
        for c in CONCLUSIONS:
            if c not in counts.columns:
                counts[c] = 0
        counts = counts[list(CONCLUSIONS)].reset_index()
        s.append(md_table(counts, [("horizon", "h"), ("model", "model")] + [(c, c) for c in CONCLUSIONS]))
        s.append("\n<details><summary>Per-asset detail</summary>\n\n")
        s.append(md_table(p, [("asset", "asset"), ("label", "label"), ("horizon", "h"), ("model", "model"),
                              ("n_pairs", "n"), ("rel_improvement", "rel. improvement"), ("ci_low", "CI low"),
                              ("ci_high", "CI high"), ("conclusion", "conclusion")], pct=("rel_improvement",)))  # fmt: skip
        s.append("\n</details>\n")
    if not cal.empty:
        s.append("\n## Calibration\n\nEmpirical coverage of central prediction intervals (nominal in the header) "
                 "and the quantile calibration error (mean |share of outcomes ≤ q_τ − τ| over all levels). "
                 "Coverage is only meaningful with a large n; a narrow interval is good only if its coverage holds.\n\n")  # fmt: skip
        ci = cal[cal["kind"] == "interval"].pivot_table(index=["horizon", "model"], columns="nominal",
                                                        values=["empirical", "width"]).reset_index()  # fmt: skip
        ci.columns = [f"{a}_{b}" if b != "" else a for a, b in ci.columns]
        qce = lb.set_index(["horizon", "model"])["qce"]
        ci["qce"] = [qce.get((h, m), math.nan) for h, m in zip(ci["horizon"], ci["model"], strict=True)]
        ci["n"] = [
            int(lb[(lb["horizon"] == h) & (lb["model"] == m)]["n"].iloc[0])
            for h, m in zip(ci["horizon"], ci["model"], strict=True)
        ]
        cc = [("horizon", "h"), ("model", "model"), ("n", "n")]
        for c in cfg.interval_levels:
            cc += [(f"empirical_{c}", f"cov {c:.0%}"), (f"width_{c}", f"width {c:.0%}")]
        cc.append(("qce", "QCE"))
        s.append(md_table(ci, cc))
    if not ot.empty:
        s.append(f"\n## Performance over time\n\nCRPS_q improvement over `{ref}` per {'year' if cfg.domain == 'stocks' else 'month'} "
                 "of origin (positive = better). A model that only wins in one period has not shown a stable advantage.\n\n")  # fmt: skip
        for h in cfg.horizons:
            o = ot[(ot["horizon"] == h) & (ot["model"] != ref)]
            if o.empty:
                continue
            piv = o.pivot_table(index="period", columns="model", values="rel_crps").reset_index()
            nper = ot[(ot["horizon"] == h) & (ot["model"] == ref)].set_index("period")["n"]
            piv["n"] = piv["period"].map(nper)
            ms = [m for m in cfg.model_names if m in piv.columns]
            s.append(f"\n**h = {h}**\n\n")
            s.append(md_table(piv, [("period", "period"), ("n", "n")] + [(m, m) for m in ms], pct=tuple(ms)))
    rsl = res["resolution"]
    if rsl.get("applicable"):
        s.append("\n## Resolution analysis (secondary, Polymarket)\n\n")
        s.append(f"Resolved markets with a YES/NO outcome: {rsl.get('n_markets', 0)} "
                 f"({rsl.get('outcomes', {})}); scored: {rsl.get('n_markets_scored', 0)}. Only origins whose cutoff is "
                 "before both the scheduled close and the recorded resolution time count. The Brier columns treat "
                 "a price as a probability of YES: `market price` is the price at the origin, `forecast price` is the "
                 "model's median forecast of the price h hours later. A price forecast is not an event-probability "
                 "model and origins of one market are strongly dependent, so with this few markets these numbers "
                 "support **no calibration claim**; they are reported for completeness and kept apart from the "
                 "price-forecast metrics above.\n\n")  # fmt: skip
        s.append(md_table(pd.DataFrame(rsl.get("rows", [])), [("horizon", "h"), ("model", "model"), ("n", "n"),
                                                             ("n_markets", "markets"), ("brier_market_price", "Brier market price"),
                                                             ("brier_forecast_price", "Brier forecast price")]))  # fmt: skip
    s.append("\n## Model runs\n\n")
    runs = pd.DataFrame(store.model_runs(eid))
    if not runs.empty:
        runs["ms_per_forecast"] = runs["inference_ms_total"] / runs["n_new_forecasts"].replace(0, np.nan)
        s.append(md_table(runs, [("id", "run"), ("model_name", "model"), ("model_version", "version"),
                                 ("device", "device"), ("status", "status"), ("n_new_forecasts", "forecasts"),
                                 ("n_failed", "failed"), ("ms_per_forecast", "ms/forecast"),
                                 ("wall_seconds", "wall s"), ("peak_rss_mb", "peak RSS MB"),
                                 ("peak_vram_mb", "peak VRAM MB"), ("code_version", "code")]))  # fmt: skip
    if figs:
        s.append("\n## Figures\n\n" + "".join(f"- [{f}]({f})\n" for f in figs))
    s.append("\n## Reading these results\n\n"
             "- `better` / `worse` mean the 95% interval of the paired loss difference excludes zero. "
             "`no demonstrated difference` means it does not: the model has not shown an advantage (this is not proof "
             "of equality). `insufficient data` means the sample is too small to tell.\n"
             "- Directional accuracy is not profitability, and no result here accounts for costs.\n"
             "- See docs/M2_RESEARCH_METHODOLOGY.md and docs/KNOWN_LIMITATIONS.md.\n")  # fmt: skip
    _ = TIMESTRAL_MODELS
    return "".join(s)


# ------------------------------------------------------------------ exports
def export(store: ResearchStore, eid: str, out_dir: Path, fmt: str = "csv") -> list[Path]:
    """Raw origins, targets and forecasts (median and quantiles per horizon), plus the metrics."""
    exp = store.get(eid)
    cfg = exp.config
    out_dir.mkdir(parents=True, exist_ok=True)
    with store.tx() as c:
        o = pd.DataFrame(
            [dict(r._mapping) for r in c.execute(select(origins).where(origins.c.experiment_id == eid))]
        )
        t = pd.DataFrame(
            [dict(r._mapping) for r in c.execute(select(targets).where(targets.c.experiment_id == eid))]
        )
        frows = c.execute(select(forecasts).where(forecasts.c.experiment_id == eid)).all()
    K = len(cfg.quantile_levels)
    recs = []
    tts = (
        {(r["asset"], r["origin_ts"]): json.loads(r["target_timestamps_json"]) for _, r in o.iterrows()}
        if not o.empty
        else {}
    )
    for r in frows:
        med = unpack(r.median, (len(cfg.horizons),))
        q = unpack(r.quantiles, (len(cfg.horizons), K))
        for j, h in enumerate(cfg.horizons):
            rec = {"model": r.model_name, "asset": r.asset, "origin_ts": r.origin_ts, "horizon": h,
                   "target_ts": tts.get((r.asset, r.origin_ts), [None] * len(cfg.horizons))[j],
                   "status": r.status, "error": r.error, "device": r.device, "inference_ms": r.inference_ms,
                   "median": None if med is None else float(med[j])}  # fmt: skip
            for k, lv in enumerate(cfg.quantile_levels):
                rec[f"q{lv:g}"] = None if q is None else float(q[j, k])
            recs.append(rec)
    f = pd.DataFrame(recs)
    res = full_analysis(store, eid)
    paths = []
    tables = {"origins": o, "targets": t, "forecasts": f, "leaderboard": res["leaderboard"],
              "comparisons": res["comparisons"], "per_asset": res["per_asset"], "calibration": res["calibration"],
              "over_time": res["over_time"]}  # fmt: skip
    for name, df in tables.items():
        p = out_dir / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(p, index=False)
        else:
            p.write_text(df.to_json(orient="records", double_precision=15, date_format="iso", indent=1))
        paths.append(p)
    (out_dir / "config.json").write_text(cfg.to_json() + "\n")
    paths.append(out_dir / "config.json")
    return paths
