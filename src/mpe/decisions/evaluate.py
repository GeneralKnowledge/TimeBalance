"""Evaluate a decision-model run against the market price and quantitative baselines.

All forecasters are scored on identical decision points with identical information cutoffs.
Anything fitted (recalibration, combination, base rate) is fitted walk-forward: a point's model
uses only markets that had *resolved* before that point's decision timestamp.

Confidence intervals use a bootstrap over markets (all leads of one market move together),
so correlated decision points of the same market are not counted as independent evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from mpe.decisions.snapshot import PricePoint, parse_iso, price_at_or_before

EPS = 0.01  # probability clip for log loss and logits (prices are quoted in cents)


@dataclass
class EvalConfig:
    min_train: int = 60  # resolved points before a walk-forward fit is used
    ridge: float = 1.0
    flat_threshold: float = 0.01  # |change| <= this is 'unchanged'
    horizons_h: tuple[int, ...] = (6, 24)
    min_edges: tuple[float, ...] = (0.02, 0.05, 0.10)
    half_spread: float = 0.01  # assumed: historical books are not available
    slippage: float = 0.005
    default_fee_rate: float = 0.0  # used when the market's own fee rate is unknown
    fee_rate_override: float | None = None  # sensitivity: apply this rate to every market
    stake_usd: float = 10.0
    max_stake_usd: float = 10.0  # liquidity constraint stand-in (no historical depth data)
    one_trade_per_market: bool = True
    contested: tuple[float, float] = (0.05, 0.95)
    bootstrap_samples: int = 2000
    seed: int = 0
    abstain_threshold: float = 0.5  # P(enough information) below this -> model abstains
    extra: dict = field(default_factory=dict)


def clip(p):
    return np.clip(np.asarray(p, dtype=np.float64), EPS, 1 - EPS)


def logit(p):
    p = clip(p)
    return np.log(p / (1 - p))


def brier(p, y):
    return (np.asarray(p, dtype=np.float64) - y) ** 2


def logloss(p, y):
    p = clip(p)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def ece(p, y, bins: int = 10) -> float:
    p, y = np.asarray(p, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if len(p) == 0:
        return float("nan")
    idx = np.minimum((p * bins).astype(int), bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return float(e)


def reliability(p, y, bins: int = 10) -> pd.DataFrame:
    p, y = np.asarray(p, dtype=np.float64), np.asarray(y, dtype=np.float64)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        rows.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int(m.sum()),
                     "mean_forecast": float(p[m].mean()) if m.any() else float("nan"),
                     "observed_yes": float(y[m].mean()) if m.any() else float("nan")})  # fmt: skip
    return pd.DataFrame(rows)


def fit_logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1.0, iters: int = 50) -> np.ndarray:
    """Ridge logistic regression by Newton's method; intercept added, not penalised."""
    X1 = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(X1.shape[1])
    pen = np.full(X1.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X1 @ w)))
        g = X1.T @ (p - y) + pen * w
        H = (X1 * (p * (1 - p))[:, None]).T @ X1 + np.diag(pen) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def walk_forward(df: pd.DataFrame, features: list[str], cfg: EvalConfig) -> np.ndarray:
    """P(YES) from a logistic model refitted for each decision time on earlier-resolved points."""
    out = np.full(len(df), np.nan)
    dts = df["decision_ts"].to_numpy()
    res = df["resolved_at"].to_numpy()
    X = df[features].to_numpy(dtype=np.float64)
    y = df["y"].to_numpy(dtype=np.float64)
    cache: dict[int, np.ndarray] = {}
    for i in range(len(df)):
        train = res < dts[i]
        n = int(train.sum())
        if n < cfg.min_train or len(np.unique(y[train])) < 2:
            continue
        if n not in cache:  # same training set for every point with the same count (sorted data)
            cache[n] = fit_logistic(X[train], y[train], cfg.ridge)
        w = cache[n]
        out[i] = 1 / (1 + np.exp(-(w[0] + X[i] @ w[1:])))
    return out


def walk_forward_base_rate(df: pd.DataFrame, cfg: EvalConfig) -> np.ndarray:
    out = np.full(len(df), np.nan)
    dts, res, y = df["decision_ts"].to_numpy(), df["resolved_at"].to_numpy(), df["y"].to_numpy()
    for i in range(len(df)):
        m = res < dts[i]
        if m.sum() >= cfg.min_train:
            out[i] = (y[m].sum() + 1) / (m.sum() + 2)
    return out


def market_bootstrap(diff: np.ndarray, groups: np.ndarray, samples: int, seed: int) -> tuple[float, float]:
    """95% CI of mean(diff) resampling whole markets."""
    if len(diff) == 0:
        return float("nan"), float("nan")
    keys, inv = np.unique(groups, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    counts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(samples, len(keys)))
    means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


# --------------------------------------------------------------------------- assembly
def assemble(outputs: list[dict], markets: dict[str, dict], cfg: EvalConfig) -> pd.DataFrame:
    rows = []
    for o in outputs:
        m = markets[o["condition_id"]]
        a = o["answers"]
        snap = o["snapshot"]

        def pp(qid, a=a):
            x = a.get(qid) or {}
            return x.get("positive_probability")

        opp = a.get("opportunity") or {}
        rows.append({
            "condition_id": o["condition_id"], "decision_ts": parse_iso(o["decision_ts"]),
            "resolved_at": parse_iso(m["resolved_at"]), "closed_time": parse_iso(m["closed_time"] or m["resolved_at"]),
            "lead_hours": o["lead_hours"], "category": m["category"] or "unknown",
            "y": 1.0 if m["outcome"] == "YES" else 0.0, "p_mkt": snap["price"]["yes"],
            "change_24h": snap["price"]["change_24h"],
            "fee_rate": m["fee_rate"], "p_laya": pp("resolves_yes"), "p_enough": pp("enough_information"),
            "laya_error": o["error"],
            "opportunity": opp.get("choice"), "opportunity_level": opp.get("expected_level"),
            "regime": (a.get("regime") or {}).get("choice"),
            **{f"dir_{h}h": (a.get(f"direction_{h}h") or {}).get("choice") for h in cfg.horizons_h},
            **{f"dirp_{h}h": (a.get(f"direction_{h}h") or {}).get("probabilities") for h in cfg.horizons_h},
        })  # fmt: skip
    df = pd.DataFrame(rows).sort_values(["decision_ts", "condition_id"]).reset_index(drop=True)
    return df


def add_forecasters(df: pd.DataFrame, cfg: EvalConfig) -> list[str]:
    ok = df["p_laya"].notna()
    df["lg_mkt"] = logit(df["p_mkt"])
    df["lg_laya"] = logit(df["p_laya"].fillna(0.5))
    df["f_market"] = clip(df["p_mkt"])
    df["f_laya_raw"] = np.where(ok, clip(df["p_laya"].fillna(0.5)), np.nan)
    df["f_base_rate"] = walk_forward_base_rate(df, cfg)
    df["f_market_recal"] = walk_forward(df, ["lg_mkt"], cfg)
    sub = df[ok]
    df.loc[ok, "f_laya_recal"] = walk_forward(sub, ["lg_laya"], cfg)
    df.loc[ok, "f_market_plus_laya"] = walk_forward(sub, ["lg_mkt", "lg_laya"], cfg)
    return ["f_market", "f_market_recal", "f_base_rate", "f_laya_raw", "f_laya_recal", "f_market_plus_laya"]


def probability_table(df: pd.DataFrame, fs: list[str], cfg: EvalConfig) -> pd.DataFrame:
    """Every forecaster on the points where *all* of them have a forecast (identical samples)."""
    common = df.dropna(subset=fs)
    rows = []
    y = common["y"].to_numpy()
    base = brier(common["f_market"], y)
    for f in fs:
        p = common[f].to_numpy()
        b = brier(p, y)
        lo, hi = market_bootstrap(
            b - base, common["condition_id"].to_numpy(), cfg.bootstrap_samples, cfg.seed
        )
        rows.append({"forecaster": f[2:], "n": len(common), "markets": common["condition_id"].nunique(),
                     "brier": b.mean(), "log_loss": logloss(p, y).mean(), "ece": ece(p, y),
                     "brier_minus_market": (b - base).mean(), "ci_low": lo, "ci_high": hi})  # fmt: skip
    return pd.DataFrame(rows)


def by_group(df: pd.DataFrame, fs: list[str], key: str) -> pd.DataFrame:
    common = df.dropna(subset=fs)
    rows = []
    for k, g in common.groupby(key):
        r = {key: k, "n": len(g)}
        for f in fs:
            r[f[2:]] = brier(g[f], g["y"]).mean()
        rows.append(r)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- direction
def direction_labels(df: pd.DataFrame, hist: dict[str, list[PricePoint]], cfg: EvalConfig) -> None:
    for h in cfg.horizons_h:
        actual = []
        for r in df.itertuples():
            t2 = r.decision_ts + pd.Timedelta(hours=h)
            if t2 > r.closed_time:
                actual.append(None)
                continue
            later = price_at_or_before(hist[r.condition_id], t2.to_pydatetime())
            if later is None:
                actual.append(None)
                continue
            d = later - r.p_mkt
            actual.append(
                "rise" if d > cfg.flat_threshold else "fall" if d < -cfg.flat_threshold else "unchanged"
            )
        df[f"actual_{h}h"] = actual


def _class_metrics(pred: pd.Series, actual: pd.Series) -> dict:
    out = {"accuracy": float((pred == actual).mean())}
    f1s = []
    for c in ("rise", "fall", "unchanged"):
        tp = ((pred == c) & (actual == c)).sum()
        prec = tp / (pred == c).sum() if (pred == c).sum() else float("nan")
        rec = tp / (actual == c).sum() if (actual == c).sum() else float("nan")
        out[f"precision_{c}"], out[f"recall_{c}"] = float(prec), float(rec)
        f1s.append(0.0 if not (prec + rec) or math.isnan(prec + rec) else 2 * prec * rec / (prec + rec))
    out["macro_f1"] = float(np.mean(f1s))
    return out


def direction_table(df: pd.DataFrame, cfg: EvalConfig) -> pd.DataFrame:
    rows = []
    for h in cfg.horizons_h:
        g = df[df[f"actual_{h}h"].notna() & df[f"dir_{h}h"].notna()].copy()
        if g.empty:
            continue
        mom = np.where(g["change_24h"].fillna(0) > cfg.flat_threshold, "rise",
                       np.where(g["change_24h"].fillna(0) < -cfg.flat_threshold, "fall", "unchanged"))  # fmt: skip
        preds = {"laya": g[f"dir_{h}h"], "persistence (unchanged)": pd.Series("unchanged", index=g.index),
                 "momentum (24h sign)": pd.Series(mom, index=g.index)}  # fmt: skip
        for name, p in preds.items():
            rows.append({"horizon_h": h, "model": name, "n": len(g), **_class_metrics(p, g[f"actual_{h}h"])})
        rows.append(
            {
                "horizon_h": h,
                "model": "share of actual classes",
                "n": len(g),
                **{
                    f"recall_{c}": float((g[f"actual_{h}h"] == c).mean())
                    for c in ("rise", "fall", "unchanged")
                },
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- trading
def simulate(df: pd.DataFrame, signal: str, cfg: EvalConfig, min_edge: float) -> dict:
    """Hold-to-resolution paper trades on the cheaper side when |signal edge| > min_edge.

    Entry pays the decision price plus an assumed half-spread and slippage, and Polymarket's taker
    fee ``shares x rate x p x (1 - p)``. Signal is a probability column, or 'opportunity'.
    """
    trades = []
    seen = set()
    cost_add = cfg.half_spread + cfg.slippage
    for r in df.sort_values("decision_ts").itertuples():
        if cfg.one_trade_per_market and r.condition_id in seen:
            continue
        if signal == "opportunity":
            side = {"strong_yes": "YES", "weak_yes": "YES", "strong_no": "NO", "weak_no": "NO"}.get(
                r.opportunity
            )
            if side is None:
                continue
            edge = float("nan")
        else:
            p = getattr(r, signal)
            if p is None or (isinstance(p, float) and math.isnan(p)):
                continue
            ask_yes, ask_no = r.p_mkt + cost_add, (1 - r.p_mkt) + cost_add
            e_yes, e_no = p - ask_yes, (1 - p) - ask_no
            side, edge = ("YES", e_yes) if e_yes >= e_no else ("NO", e_no)
            if edge <= min_edge:
                continue
        price = min((r.p_mkt if side == "YES" else 1 - r.p_mkt) + cost_add, 0.99)
        stake = min(cfg.stake_usd, cfg.max_stake_usd)
        shares = stake / price
        rate = (
            cfg.fee_rate_override
            if cfg.fee_rate_override is not None
            else (
                r.fee_rate if r.fee_rate is not None and not math.isnan(r.fee_rate) else cfg.default_fee_rate
            )
        )
        fee = shares * rate * price * (1 - price)
        win = (r.y == 1.0) == (side == "YES")
        pnl = (shares if win else 0.0) - stake - fee
        seen.add(r.condition_id)
        trades.append({"resolved_at": r.resolved_at, "pnl": pnl, "win": win, "stake": stake, "edge": edge,
                       "lead_hours": r.lead_hours, "category": r.category})  # fmt: skip
    if not trades:
        return {"signal": signal, "min_edge": min_edge, "trades": 0}
    t = pd.DataFrame(trades).sort_values("resolved_at")
    eq = t["pnl"].cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max())
    return {"signal": signal, "min_edge": min_edge, "trades": len(t), "net_pnl": float(t["pnl"].sum()),
            "return_on_turnover": float(t["pnl"].sum() / t["stake"].sum()), "win_rate": float(t["win"].mean()),
            "turnover": float(t["stake"].sum()), "avg_edge": float(t["edge"].mean()),
            "max_drawdown": dd,
            "by_lead": t.groupby("lead_hours")["pnl"].agg(["count", "sum"]).reset_index().to_dict("records"),
            "by_category": t.groupby("category")["pnl"].agg(["count", "sum"]).reset_index().to_dict("records")}  # fmt: skip


# --------------------------------------------------------------------------- disagreement
def disagreement(df: pd.DataFrame, col: str, cfg: EvalConfig) -> dict:
    g = df.dropna(subset=[col, "f_market_recal"]).copy()
    if g.empty:
        return {"n": 0}
    g["d"] = g[col] - g["p_mkt"]
    g["d_quant"] = g["f_market_recal"] - g["p_mkt"]
    g["surprise"] = g["y"] - g["p_mkt"]
    g["bucket"] = pd.cut(g["d"].abs(), [0, 0.05, 0.10, 0.20, 1.0], include_lowest=True).astype(str)
    rows = []
    for b, x in g.groupby("bucket"):
        rows.append(
            {
                "abs_disagreement": b,
                "n": len(x),
                "laya_direction_right": float((np.sign(x["d"]) == np.sign(x["surprise"])).mean()),
                "brier_market": brier(x["p_mkt"], x["y"]).mean(),
                "brier_laya": brier(x[col], x["y"]).mean(),
            }
        )
    corr = float(np.corrcoef(g["d"], g["surprise"])[0, 1]) if g["d"].std() > 0 else float("nan")
    # Bootstrap the correlation over markets
    keys = g["condition_id"].unique()
    rng = np.random.default_rng(cfg.seed)
    by = {k: x for k, x in g.groupby("condition_id")}
    cs = []
    for _ in range(min(cfg.bootstrap_samples, 500)):
        s = pd.concat([by[k] for k in rng.choice(keys, len(keys))])
        if s["d"].std() > 0 and s["surprise"].std() > 0:
            cs.append(np.corrcoef(s["d"], s["surprise"])[0, 1])
    return {"n": len(g), "corr_disagreement_vs_market_error": corr,
            "corr_ci": [float(np.quantile(cs, 0.025)), float(np.quantile(cs, 0.975))] if cs else None,
            "corr_quant_baseline_vs_market_error": float(np.corrcoef(g["d_quant"], g["surprise"])[0, 1])
            if g["d_quant"].std() > 0 else float("nan"),
            "corr_laya_vs_quant_disagreement": float(np.corrcoef(g["d"], g["d_quant"])[0, 1])
            if g["d"].std() > 0 and g["d_quant"].std() > 0 else float("nan"),
            "buckets": rows}  # fmt: skip


def regime_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df[df["regime"].notna()].copy()
    if g.empty:
        return pd.DataFrame()
    return (g.groupby("regime").agg(n=("y", "size"), mean_past_24h_change=("change_24h", "mean"))
            .reset_index())  # fmt: skip


def evaluate(outputs: list[dict], markets: dict[str, dict], hist: dict[str, list[PricePoint]],
             cfg: EvalConfig) -> dict:  # fmt: skip
    df = assemble(outputs, markets, cfg)
    fs = add_forecasters(df, cfg)
    direction_labels(df, hist, cfg)
    lo, hi = cfg.contested
    contested = df[(df["p_mkt"] >= lo) & (df["p_mkt"] <= hi)]
    abstain = df["p_enough"].notna() & (df["p_enough"] < cfg.abstain_threshold)
    trading = [simulate(df, s, cfg, e) for s in ("f_laya_raw", "f_laya_recal", "f_market_plus_laya",
                                                 "f_market_recal") for e in cfg.min_edges]  # fmt: skip
    trading.append(simulate(df, "opportunity", cfg, 0.0))
    common = df.dropna(subset=fs)
    return {
        "frame": df,
        "points": len(df),
        "markets": int(df["condition_id"].nunique()),
        "errors": int(df["laya_error"].notna().sum()),
        "period": [str(df["decision_ts"].min()), str(df["decision_ts"].max())],
        "probability": probability_table(df, fs, cfg),
        "probability_contested": probability_table(contested, fs, cfg) if len(contested) else pd.DataFrame(),
        "probability_answered": probability_table(df[~abstain], fs, cfg),
        "abstained": int(abstain.sum()),
        "by_lead": by_group(df, fs, "lead_hours"),
        "by_category": by_group(df, fs, "category"),
        "reliability": {
            f[2:]: reliability(common[f], common["y"]) for f in ("f_market", "f_laya_raw", "f_laya_recal")
        },
        "laya_raw_distribution": np.histogram(df["p_laya"].dropna(), bins=10, range=(0, 1))[0].tolist(),
        "laya_vs_market_corr": float(df[["p_laya", "p_mkt"]].dropna().corr().iloc[0, 1])
        if df["p_laya"].notna().sum() > 2
        else float("nan"),
        "direction": direction_table(df, cfg),
        "trading": trading,
        "disagreement_raw": disagreement(df, "f_laya_raw", cfg),
        "disagreement_recal": disagreement(df, "f_laya_recal", cfg),
        "regime": regime_table(df),
        "opportunity_counts": df["opportunity"].value_counts().to_dict(),
    }
