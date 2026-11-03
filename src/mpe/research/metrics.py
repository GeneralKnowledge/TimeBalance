"""Forecast scores. Pure numpy functions, identical for every model.

Conventions (docs/M2_RESEARCH_METHODOLOGY.md):

* error = forecast - actual, so a positive mean signed error is over-forecasting.
* The point forecast is the median (0.5 quantile).
* Pinball loss at level tau for quantile forecast q and outcome y:
  ``rho_tau(y - q) = max(tau * (y - q), (tau - 1) * (y - q))``.
* ``crps_q`` is a quantile-based CRPS approximation restricted to the forecast's level range
  ``[tau_1, tau_K]``: ``2 * integral_{tau_1}^{tau_K} rho_tau(y - q_tau) dtau``, integrated with the
  trapezoidal rule over the given (possibly uneven) levels. Nothing is extrapolated into the
  tails, so it omits the tail mass below tau_1 and above tau_K and is not the full CRPS. It is
  comparable across models only on the same level set, which every experiment enforces.
* Directional accuracy compares signs of predicted and actual *changes*; pairs where either
  change is exactly zero are excluded from the denominator and counted separately.
"""

from __future__ import annotations

import math

import numpy as np


def pinball(y: np.ndarray, q: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """(N, K) pinball losses for outcomes y (N,) and quantile forecasts q (N, K)."""
    y = np.asarray(y, dtype=np.float64)[:, None]
    q = np.asarray(q, dtype=np.float64)
    tau = np.asarray(levels, dtype=np.float64)[None, :]
    d = y - q
    return np.maximum(tau * d, (tau - 1.0) * d)


def crps_quantile(y: np.ndarray, q: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """(N,) truncated quantile CRPS: 2 * trapezoid of pinball loss over the levels."""
    lv = np.asarray(levels, dtype=np.float64)
    if lv.ndim != 1 or len(lv) < 2 or not (np.diff(lv) > 0).all():
        raise ValueError("need at least two strictly increasing levels")
    pl = pinball(y, q, lv)
    w = np.diff(lv)
    return 2.0 * ((pl[:, 1:] + pl[:, :-1]) / 2.0 * w).sum(axis=1)


def central_interval(levels: list[float], coverage: float) -> tuple[int, int]:
    """Indices of the (1-c)/2 and (1+c)/2 levels."""
    lo, hi = round((1 - coverage) / 2, 10), round((1 + coverage) / 2, 10)
    lv = [round(x, 10) for x in levels]
    return lv.index(lo), lv.index(hi)


def covered(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Boolean (N,): lo <= y <= hi (closed interval)."""
    return (y >= lo) & (y <= hi)


def directional(pred_change: np.ndarray, actual_change: np.ndarray) -> dict:
    p = np.sign(np.asarray(pred_change, dtype=np.float64))
    a = np.sign(np.asarray(actual_change, dtype=np.float64))
    valid = (p != 0) & (a != 0)
    n = int(valid.sum())
    hits = int((p[valid] == a[valid]).sum())
    return {"hits": hits, "n": n, "accuracy": hits / n if n else float("nan"),
            "actual_zero": int((a == 0).sum()), "pred_zero": int(((p == 0) & (a != 0)).sum())}  # fmt: skip


def point_summary(err: np.ndarray) -> dict:
    e = np.asarray(err, dtype=np.float64)
    if not len(e):
        return {
            "n": 0,
            "mae": float("nan"),
            "rmse": float("nan"),
            "mse": float("nan"),
            "mean_error": float("nan"),
        }
    return {"n": len(e), "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e**2).mean())),
            "mse": float((e**2).mean()), "mean_error": float(e.mean())}  # fmt: skip


def quantile_calibration(y: np.ndarray, q: np.ndarray, levels: np.ndarray) -> dict:
    """Empirical frequency of y <= q_tau per level, and the mean absolute deviation from tau."""
    freq = (np.asarray(y)[:, None] <= np.asarray(q)).mean(axis=0)
    lv = np.asarray(levels)
    return {"levels": lv.tolist(), "frequency": freq.tolist(), "qce": float(np.abs(freq - lv).mean())}


def moving_block_bootstrap_mean(
    d: np.ndarray, block: int, samples: int, seed: int, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile CI for the mean of a time-ordered series ``d`` using a moving-block bootstrap.

    Blocks of ``block`` consecutive values are drawn with replacement (start uniformly in
    [0, n - block]) until n values are collected, preserving dependence within blocks.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    if n == 0:
        return float("nan"), float("nan")
    block = int(max(1, min(block, n)))
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(samples, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(samples, -1)[:, :n]
    means = d[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def interval_score(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, coverage: float) -> np.ndarray:
    """(N,) interval (Winkler) score of the central ``coverage`` interval [lo, hi]; lower is better.

    ``(hi - lo) + (2 / a) * (lo - y) * [y < lo] + (2 / a) * (y - hi) * [y > hi]`` with ``a = 1 - coverage``
    (Gneiting and Raftery 2007, section 6.2). A proper score: width and misses in one number.
    """
    a = 1.0 - coverage
    y, lo, hi = (np.asarray(v, dtype=np.float64) for v in (y, lo, hi))
    return (hi - lo) + (2.0 / a) * np.clip(lo - y, 0, None) + (2.0 / a) * np.clip(y - hi, 0, None)


def pit_histogram(below: np.ndarray, levels: np.ndarray) -> dict:
    """Share of outcomes in each bin between consecutive quantile levels (plus the two tails).

    ``below`` is (N, K) booleans ``y <= q_k``. For a calibrated forecast each bin's share equals
    its width in probability. Returns edges, observed and expected shares, and the total
    variation distance 0.5 * sum |observed - expected| (0 = perfectly calibrated).
    """
    lv = np.asarray(levels, dtype=np.float64)
    if not len(below):
        return {"edges": [], "observed": [], "expected": [], "tv_distance": float("nan"), "n": 0}
    cdf = np.concatenate([[0.0], below.mean(axis=0), [1.0]])
    edges = np.concatenate([[0.0], lv, [1.0]])
    obs = np.diff(cdf)
    exp = np.diff(edges)
    return {"edges": edges.tolist(), "observed": obs.tolist(), "expected": exp.tolist(),
            "tv_distance": float(0.5 * np.abs(obs - exp).sum()), "n": len(below)}  # fmt: skip


def newey_west_variance(d: np.ndarray, bandwidth: int) -> float:
    """Long-run variance of the mean's numerator: gamma_0 + 2 * sum_k (1 - k/(L+1)) gamma_k (Bartlett)."""
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    e = d - d.mean()
    v = float(e @ e) / n
    for k in range(1, min(bandwidth, n - 1) + 1):
        v += 2.0 * (1.0 - k / (bandwidth + 1.0)) * float(e[k:] @ e[:-k]) / n
    return v


def diebold_mariano(d: np.ndarray, h: int) -> dict:
    """Diebold-Mariano test of E[d] = 0 for a time-ordered loss differential ``d``.

    Newey-West (Bartlett) long-run variance with bandwidth h - 1 and the Harvey-Leybourne-Newbold
    (1997) small-sample factor. ``h`` is the overlap of consecutive targets in steps of ``d``.
    The two-sided p-value uses the normal distribution (no scipy dependency); for the
    sample sizes where a result is reported here (>= 30 dates) the t(n-1) reference the HLN
    paper uses differs from it in the third decimal at most for p around 0.05.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    if n < 5 or h < 1 or h >= n:
        return {"statistic": float("nan"), "pvalue": float("nan"), "n": n}
    lrv = newey_west_variance(d, h - 1)
    mean = float(d.mean())
    if lrv <= 0:
        return {"statistic": 0.0 if mean == 0 else math.copysign(math.inf, mean),
                "pvalue": 1.0 if mean == 0 else 0.0, "n": n}  # fmt: skip
    stat = mean / math.sqrt(lrv / n)
    hln = math.sqrt(max((n + 1 - 2 * h + h * (h - 1) / n) / n, 0.0))
    stat *= hln
    p = math.erfc(abs(stat) / math.sqrt(2.0))
    return {"statistic": stat, "pvalue": p, "n": n}


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (family-wise error); NaN stays NaN."""
    idx = [i for i, p in enumerate(pvalues) if not math.isnan(p)]
    m = len(idx)
    out = [float("nan")] * len(pvalues)
    running = 0.0
    for rank, i in enumerate(sorted(idx, key=lambda j: pvalues[j])):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        out[i] = running
    return out
