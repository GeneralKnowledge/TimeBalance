"""Scoring, aggregation, paired comparisons and calibration for a stored experiment.

Nothing here reads market data: it joins stored forecasts with stored realised targets.

Aggregation rules (also in docs/M2_RESEARCH_METHODOLOGY.md):

* Every model is scored on the **common sample**: the (asset, origin, horizon) cases where every
  model in the experiment produced a valid forecast and the realised target exists. Cases that
  fail for one model are reported, not silently dropped for that model alone.
* ``pooled`` metrics weight every scored case equally; ``macro`` metrics are the unweighted mean of
  the per-asset metrics, so an asset with many origins does not dominate. Both are reported.
* Paired comparisons use per-case loss differences against the reference baseline (and the best
  baseline), with a moving-block bootstrap over origin dates: all assets at one origin date stay
  together, and the block length covers the overlap of multi-step targets.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import select

from mpe.features.transforms import inv_logit
from mpe.research import metrics as M
from mpe.research.config import BASELINE_MODELS, TIMESTRAL_MODELS, ExperimentConfig
from mpe.research.store import ResearchStore, forecasts, origins, targets

LOSSES = {"mae": "abs_err", "mse": "sq_err", "crps": "crps"}


@dataclass
class Scored:
    cfg: ExperimentConfig
    rows: pd.DataFrame  # one row per (model, asset, origin, horizon) in the common sample
    below: np.ndarray  # (len(rows), K) bool: y <= q_k
    exclusions: dict
    meta: dict  # per-asset metadata from preparation


def load_scored(store: ResearchStore, eid: str) -> Scored:
    exp = store.get(eid)
    cfg = exp.config
    hz = cfg.horizons
    levels = np.asarray(cfg.quantile_levels)
    K = len(levels)
    with store.tx() as c:
        orows = c.execute(select(origins).where(origins.c.experiment_id == eid)).all()
        trows = c.execute(select(targets).where(targets.c.experiment_id == eid)).all()
        frows = c.execute(select(forecasts.c.model_name, forecasts.c.asset, forecasts.c.origin_ts,
                                 forecasts.c.status, forecasts.c.error, forecasts.c.median, forecasts.c.quantiles)
                          .where(forecasts.c.experiment_id == eid)).all()  # fmt: skip
    tmap = {(r.asset, r.target_ts): r for r in trows}
    ok_origins = {(r.asset, r.origin_ts): r for r in orows if r.status == "ok"}
    excl: dict = {"origins": {}, "targets": {}, "forecast_failures": {}, "failure_examples": {},
                  "skipped_grid_origins": {}, "excluded_assets": (exp.prepare or {}).get("excluded_assets", [])}  # fmt: skip
    for r in orows:
        if r.status != "ok":
            excl["origins"][r.reason] = excl["origins"].get(r.reason, 0) + 1
    for a, info in ((exp.prepare or {}).get("assets") or {}).items():
        for k, v in (info.get("skipped") or {}).items():
            excl["skipped_grid_origins"][k] = excl["skipped_grid_origins"].get(k, 0) + v
    # realised targets per (origin, horizon): model independent
    case_y: dict[tuple[str, str, int], tuple[float, float, str]] = {}
    for (a, o), r in ok_origins.items():
        tts = json.loads(r.target_timestamps_json)
        for h, t in zip(hz, tts, strict=True):
            tr = tmap.get((a, t))
            status = tr.status if tr is not None else "target_missing"
            if tr is None or tr.value is None or status != "observed":
                key = f"h{h}:{status}"
                excl["targets"][key] = excl["targets"].get(key, 0) + 1
                continue
            case_y[(a, o, h)] = (tr.value, tr.level, t)
    # forecasts (decoded in bulk: an experiment can hold hundreds of thousands)
    models = cfg.model_names
    ok_rows = [r for r in frows if r.status == "ok"]
    ok_by_model: dict[str, set] = {m: set() for m in models}
    for r in frows:
        if r.status != "ok":
            excl["forecast_failures"][r.model_name] = excl["forecast_failures"].get(r.model_name, 0) + 1
            ex = excl["failure_examples"].setdefault(r.model_name, [])
            if len(ex) < 3:
                ex.append({"asset": r.asset, "origin": r.origin_ts, "error": r.error})
            continue
        ok_by_model.setdefault(r.model_name, set()).add((r.asset, r.origin_ts))
    common_origins = set.intersection(*(ok_by_model[m] for m in models)) if models else set()
    missing_any = set().union(*ok_by_model.values()) - common_origins if ok_by_model else set()
    excl["origins_without_all_models"] = len(missing_any)
    excl["not_yet_forecast"] = {m: len(set(ok_origins) - ok_by_model[m]) for m in models}
    nH = len(hz)
    med = np.frombuffer(b"".join(r.median for r in ok_rows), dtype="<f8").reshape(-1, nH)
    qa = np.frombuffer(b"".join(r.quantiles for r in ok_rows), dtype="<f8").reshape(-1, nH, K)
    fdf = pd.DataFrame({"model": [r.model_name for r in ok_rows], "asset": [r.asset for r in ok_rows],
                        "origin_ts": [r.origin_ts for r in ok_rows], "fidx": np.arange(len(ok_rows))})  # fmt: skip
    keep = [(a, o) in common_origins for a, o in zip(fdf["asset"], fdf["origin_ts"], strict=True)]
    fdf = fdf[np.asarray(keep, dtype=bool)]
    cases = pd.DataFrame(
        [(a, o, j, h, yy[2], yy[0], yy[1], ok_origins[(a, o)].last_value, ok_origins[(a, o)].last_level)
         for (a, o, h), yy in case_y.items() for j in [hz.index(h)]],
        columns=["asset", "origin_ts", "hidx", "horizon", "target_ts", "y", "y_level", "last_value", "last_level"],
    )  # fmt: skip
    keys = {"asset": object, "origin_ts": object}
    df = fdf.astype(keys).merge(cases.astype(keys), on=["asset", "origin_ts"], how="inner")
    order = {m: i for i, m in enumerate(models)}
    df = (
        df.assign(_m=df["model"].map(order))
        .sort_values(["_m", "asset", "origin_ts", "horizon"])
        .drop(columns="_m")
    )
    df = df.reset_index(drop=True)
    fi, hi = df["fidx"].to_numpy(), df["hidx"].to_numpy()
    df["yhat"] = med[fi, hi] if len(df) else np.zeros(0)
    Q = qa[fi, hi, :] if len(df) else np.zeros((0, K))
    df = df.drop(columns=["fidx", "hidx"])
    df["origin_ts"] = pd.to_datetime(df["origin_ts"], utc=True)
    df["target_ts"] = pd.to_datetime(df["target_ts"], utc=True)
    below = _score(df, Q, cfg, levels)
    return Scored(cfg, df, below, excl, (exp.prepare or {}).get("assets") or {})


def _score(df: pd.DataFrame, Q: np.ndarray, cfg: ExperimentConfig, levels: np.ndarray) -> np.ndarray:
    if df.empty:
        return np.zeros((0, len(levels)), dtype=bool)
    y = df["y"].to_numpy()
    yhat = df["yhat"].to_numpy()
    df["err"] = yhat - y
    df["abs_err"] = np.abs(df["err"])
    df["sq_err"] = df["err"] ** 2
    pl = M.pinball(y, Q, levels)
    df["pinball"] = pl.mean(axis=1)
    df["crps"] = M.crps_quantile(y, Q, levels)
    for c in cfg.interval_levels:
        lo, hi = M.central_interval(cfg.quantile_levels, c)
        df[f"cov_{c:g}"] = M.covered(y, Q[:, lo], Q[:, hi]).astype(float)
        df[f"width_{c:g}"] = Q[:, hi] - Q[:, lo]
        df[f"is_{c:g}"] = M.interval_score(y, Q[:, lo], Q[:, hi], c)
    if cfg.target == "log_return":
        df["pred_change"], df["actual_change"] = yhat, y
    else:
        last = df["last_value"].to_numpy()
        df["pred_change"], df["actual_change"] = yhat - last, y - last
        eps = cfg.logit_eps
        p = inv_logit(y, eps)
        phat = inv_logit(yhat, eps)
        df["p"], df["phat"] = p, phat
        df["abs_err_p"] = np.abs(phat - p)
        df["sq_err_p"] = (phat - p) ** 2
        Qp = inv_logit(Q, eps)  # monotone transform: quantiles map to quantiles
        df["pinball_p"] = M.pinball(p, Qp, levels).mean(axis=1)
        df["crps_p"] = M.crps_quantile(p, Qp, levels)
    return y[:, None] <= Q


# ------------------------------------------------------------------ summaries
def summarise(g: pd.DataFrame, below: np.ndarray | None, cfg: ExperimentConfig) -> dict:
    out: dict = M.point_summary(g["err"].to_numpy())
    d = M.directional(g["pred_change"].to_numpy(), g["actual_change"].to_numpy())
    out.update(
        dir_acc=d["accuracy"], dir_n=d["n"], dir_actual_zero=d["actual_zero"], dir_pred_zero=d["pred_zero"]
    )
    out["pinball"] = float(g["pinball"].mean()) if len(g) else math.nan
    out["crps"] = float(g["crps"].mean()) if len(g) else math.nan
    for c in cfg.interval_levels:
        out[f"cov_{c:g}"] = float(g[f"cov_{c:g}"].mean()) if len(g) else math.nan
        out[f"width_{c:g}"] = float(g[f"width_{c:g}"].mean()) if len(g) else math.nan
        out[f"is_{c:g}"] = float(g[f"is_{c:g}"].mean()) if len(g) else math.nan
    if below is not None and len(below):
        freq = below.mean(axis=0)
        out["qce"] = float(np.abs(freq - np.asarray(cfg.quantile_levels)).mean())
        out["pit_tv"] = M.pit_histogram(below, np.asarray(cfg.quantile_levels))["tv_distance"]
    if "abs_err_p" in g:
        out["mae_p"] = float(g["abs_err_p"].mean()) if len(g) else math.nan
        out["rmse_p"] = float(np.sqrt(g["sq_err_p"].mean())) if len(g) else math.nan
        out["pinball_p"] = float(g["pinball_p"].mean()) if len(g) else math.nan
        out["crps_p"] = float(g["crps_p"].mean()) if len(g) else math.nan
    out["n_assets"] = int(g["asset"].nunique())
    out["n_origins"] = int(g["origin_ts"].nunique())
    return out


def _groups(sc: Scored, keys: list[str]):
    df = sc.rows
    if df.empty:
        return
    for k, idx in df.groupby(keys, sort=True).indices.items():
        yield (k if isinstance(k, tuple) else (k,)), df.iloc[idx], sc.below[idx]


def leaderboard(sc: Scored) -> pd.DataFrame:
    """Per (horizon, model): pooled metrics, macro-averaged metrics, and relative improvement."""
    cfg = sc.cfg
    rows = []
    for (h, m), g, b in _groups(sc, ["horizon", "model"]):
        s = summarise(g, b, cfg)
        per_asset = [summarise(ga, None, cfg) for _, ga in g.groupby("asset")]
        s["macro_mae"] = float(np.mean([p["mae"] for p in per_asset]))
        s["macro_crps"] = float(np.mean([p["crps"] for p in per_asset]))
        s["macro_cov_0.9"] = float(np.mean([p.get("cov_0.9", math.nan) for p in per_asset]))
        rows.append({"horizon": h, "model": m, **s})
    lb = pd.DataFrame(rows)
    if lb.empty:
        return lb
    ref = lb[lb["model"] == cfg.reference_baseline].set_index("horizon")
    for metric in ("mae", "rmse", "crps", "pinball", "macro_mae", "macro_crps"):
        base = lb["horizon"].map(ref[metric])
        lb[f"rel_{metric}"] = 1.0 - lb[metric] / base  # > 0 = better than the reference
    # scale-free: skill against the reference within each asset, then the unweighted mean over
    # assets, so high-volatility assets do not dominate the way they do in pooled losses
    per = sc.rows.groupby(["horizon", "model", "asset"])[["abs_err", "crps"]].mean()
    refa = per.xs(cfg.reference_baseline, level="model")
    for col, name in (("abs_err", "asset_skill_mae"), ("crps", "asset_skill_crps")):
        sk = 1.0 - per[col] / refa[col].reindex(per.index.droplevel("model")).to_numpy()
        avg = sk.groupby(level=["horizon", "model"]).mean()
        lb[name] = [avg.get((h, m), math.nan) for h, m in zip(lb["horizon"], lb["model"], strict=True)]
    lb["model_order"] = lb["model"].map({m: i for i, m in enumerate(cfg.model_names)})
    return lb.sort_values(["horizon", "model_order"]).drop(columns="model_order").reset_index(drop=True)


def _block_len(cfg: ExperimentConfig, h: int, n_dates: int) -> int:
    overlap = math.ceil(h / cfg.origin_stride)
    return max(1, overlap, math.ceil(n_dates ** (1 / 3)))


def paired(sc: Scored, model: str, ref: str, h: int, loss: str, df: pd.DataFrame | None = None) -> dict:
    """Mean loss difference model - ref over the same cases, with a moving-block bootstrap CI."""
    cfg = sc.cfg
    d = sc.rows if df is None else df
    d = d[d["horizon"] == h]
    col = LOSSES[loss]
    a = d[d["model"] == model].set_index(["asset", "origin_ts"])[col]
    b = d[d["model"] == ref].set_index(["asset", "origin_ts"])[col]
    a, b = a.align(b, join="inner")
    out = {"model": model, "reference": ref, "horizon": h, "loss": loss, "n_pairs": len(a),
           "ci_low": math.nan, "ci_high": math.nan, "dm_stat": math.nan, "dm_p": math.nan}  # fmt: skip
    if not len(a):
        return {**out, "conclusion": "insufficient data", "mean_diff": math.nan}
    diff = (a - b).rename("d").reset_index()
    by_date = diff.groupby("origin_ts")["d"].agg(["sum", "count"]).sort_index()
    n_dates = len(by_date)
    L = _block_len(cfg, h, n_dates)
    mean_diff = float(diff["d"].mean())
    ref_mean = float(b.mean())
    out.update(n_assets=int(diff["asset"].nunique()), n_dates=n_dates, block=L, mean_diff=mean_diff,
               ref_loss=ref_mean, model_loss=float(a.mean()),
               rel_improvement=-mean_diff / ref_mean if ref_mean else math.nan)  # fmt: skip
    if n_dates < cfg.min_paired_dates or n_dates / L < 10:
        out.update(ci_low=math.nan, ci_high=math.nan, conclusion="insufficient data")
        return out
    lo, hi = _ratio_bootstrap(by_date["sum"].to_numpy(), by_date["count"].to_numpy(), L, cfg.bootstrap_samples,
                              cfg.seed)  # fmt: skip
    concl = "better" if hi < 0 else "worse" if lo > 0 else "no demonstrated difference"
    dm = M.diebold_mariano((by_date["sum"] / by_date["count"]).to_numpy(), math.ceil(h / cfg.origin_stride))
    out.update(ci_low=lo, ci_high=hi, conclusion=concl, dm_stat=dm["statistic"], dm_p=dm["pvalue"])
    return out


def _ratio_bootstrap(sums: np.ndarray, counts: np.ndarray, block: int, samples: int, seed: int,
                     alpha: float = 0.05) -> tuple[float, float]:  # fmt: skip
    """Moving-block bootstrap over dates of the pooled mean sum(d)/count."""
    n = len(sums)
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    k = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(samples, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(samples, -1)[:, :n]
    est = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(np.quantile(est, alpha / 2)), float(np.quantile(est, 1 - alpha / 2))


def comparisons(sc: Scored, lb: pd.DataFrame) -> pd.DataFrame:
    """Every Timestral model vs the reference and vs the best baseline, per horizon and loss."""
    cfg = sc.cfg
    rows = []
    tim = [m for m in cfg.model_names if m in TIMESTRAL_MODELS]
    bases = [m for m in cfg.model_names if m in BASELINE_MODELS]
    for h in cfg.horizons:
        lbh = lb[lb["horizon"] == h]
        for loss in ("mae", "crps"):
            metric = "mae" if loss == "mae" else "crps"
            best = lbh[lbh["model"].isin(bases)].sort_values(metric)["model"].head(1).tolist()
            for m in tim:
                rows.append({**paired(sc, m, cfg.reference_baseline, h, loss), "against": "reference"})
                if best and best[0] != cfg.reference_baseline:
                    rows.append({**paired(sc, m, best[0], h, loss), "against": "best baseline"})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["dm_p_holm"] = M.holm(out["dm_p"].astype(float).tolist())  # family = this whole table
    return out


def per_asset(sc: Scored) -> pd.DataFrame:
    """Each Timestral model vs the reference per asset and horizon (CRPS and MAE), with conclusions."""
    cfg = sc.cfg
    rows = []
    tim = [m for m in cfg.model_names if m in TIMESTRAL_MODELS] or [
        m for m in cfg.model_names if m != cfg.reference_baseline]  # fmt: skip
    for (a,), g, _ in _groups(sc, ["asset"]):
        for h in cfg.horizons:
            for m in tim:
                for loss in ("crps", "mae"):
                    r = paired(sc, m, cfg.reference_baseline, h, loss, df=g)
                    rows.append({"asset": a, "label": (sc.meta.get(a) or {}).get("label", a), **r})
    return pd.DataFrame(rows)


def calibration(sc: Scored) -> pd.DataFrame:
    cfg = sc.cfg
    rows = []
    for (h, m), g, b in _groups(sc, ["horizon", "model"]):
        freq = b.mean(axis=0)
        for c in cfg.interval_levels:
            rows.append({"horizon": h, "model": m, "kind": "interval", "nominal": c,
                         "empirical": float(g[f"cov_{c:g}"].mean()), "width": float(g[f"width_{c:g}"].mean()),
                         "n": len(g)})  # fmt: skip
        for lv, f in zip(cfg.quantile_levels, freq, strict=True):
            rows.append({"horizon": h, "model": m, "kind": "quantile", "nominal": lv, "empirical": float(f),
                         "width": math.nan, "n": len(g)})  # fmt: skip
        pit = M.pit_histogram(b, np.asarray(cfg.quantile_levels))
        for lo, hi, ob, ex in zip(
            pit["edges"][:-1], pit["edges"][1:], pit["observed"], pit["expected"], strict=True
        ):
            rows.append({"horizon": h, "model": m, "kind": "pit_bin", "nominal": (lo + hi) / 2, "empirical": ob,
                         "expected": ex, "bin_lo": lo, "bin_hi": hi, "width": math.nan, "n": len(g)})  # fmt: skip
    return pd.DataFrame(rows)


def over_time(sc: Scored) -> pd.DataFrame:
    cfg = sc.cfg
    df = sc.rows
    if df.empty:
        return pd.DataFrame()
    freq = "Y" if cfg.domain == "stocks" else "M"
    period = df["origin_ts"].dt.tz_convert(None).dt.to_period(freq).astype(str)
    g = df.assign(period=period).groupby(["horizon", "period", "model"])
    out = g.agg(n=("err", "size"), mae=("abs_err", "mean"), crps=("crps", "mean"),
                cov90=("cov_0.9", "mean") if "cov_0.9" in df else ("crps", "size")).reset_index()  # fmt: skip
    ref = out[out["model"] == cfg.reference_baseline].set_index(["horizon", "period"])
    key = pd.MultiIndex.from_frame(out[["horizon", "period"]])
    out["rel_mae"] = 1 - out["mae"].to_numpy() / ref["mae"].reindex(key).to_numpy()
    out["rel_crps"] = 1 - out["crps"].to_numpy() / ref["crps"].reindex(key).to_numpy()
    return out


def resolution_analysis(sc: Scored) -> dict:
    """Secondary Polymarket analysis against eventual YES/NO outcomes (resolved markets only).

    Origins count only if their cutoff is before both the scheduled close and the recorded
    resolution time. Brier scores compare (a) the market price at the origin and (b) each model's
    forecast price at the horizon, both read as a probability of YES. A price forecast is not an
    event-probability model, so these are descriptive comparisons, not calibration claims.
    """
    cfg = sc.cfg
    if cfg.domain != "polymarket" or sc.rows.empty:
        return {"applicable": False}
    res = {}
    for a, info in sc.meta.items():
        r = ((info.get("meta") or {}).get("resolution")) or None
        if r and r.get("outcome") in ("YES", "NO"):
            close = (info.get("meta") or {}).get("closing_time")
            bound = min(
                pd.Timestamp(r["resolved_at"]),
                pd.Timestamp(close) if close else pd.Timestamp(r["resolved_at"]),
            )
            res[a] = (1.0 if r["outcome"] == "YES" else 0.0, bound)
    df = sc.rows[sc.rows["asset"].isin(res)].copy()
    if df.empty:
        return {"applicable": True, "n_markets": 0, "rows": []}
    df["outcome"] = df["asset"].map(lambda a: res[a][0])
    df["bound"] = df["asset"].map(lambda a: res[a][1])
    cutoff = df["origin_ts"] + pd.Timedelta(seconds=cfg.cutoff_delay_seconds)
    df = df[cutoff < df["bound"]]
    rows = []
    for (h, m), g in df.groupby(["horizon", "model"]):
        o = g["outcome"].to_numpy()
        p0 = np.clip(g["last_level"].to_numpy(), cfg.logit_eps, 1 - cfg.logit_eps)
        rows.append({"horizon": h, "model": m, "n": len(g), "n_markets": g["asset"].nunique(),
                     "brier_market_price": float(((p0 - o) ** 2).mean()),
                     "brier_forecast_price": float(((g["phat"].to_numpy() - o) ** 2).mean())})  # fmt: skip
    return {"applicable": True, "n_markets": len(res), "n_markets_scored": int(df["asset"].nunique()),
            "outcomes": {"YES": int(sum(v[0] == 1 for v in res.values())),
                         "NO": int(sum(v[0] == 0 for v in res.values()))},
            "rows": rows}  # fmt: skip


def full_analysis(store: ResearchStore, eid: str) -> dict:
    sc = load_scored(store, eid)
    lb = leaderboard(sc)
    return {"scored": sc, "leaderboard": lb, "comparisons": comparisons(sc, lb) if not lb.empty else pd.DataFrame(),
            "per_asset": per_asset(sc), "calibration": calibration(sc), "over_time": over_time(sc),
            "resolution": resolution_analysis(sc)}  # fmt: skip
