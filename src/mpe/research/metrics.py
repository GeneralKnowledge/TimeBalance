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
