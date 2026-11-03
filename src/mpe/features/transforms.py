"""Target transforms: log returns for prices, logit for prediction-market YES prices."""

from __future__ import annotations

import numpy as np

DEFAULT_EPS = 1e-4


def log_returns(prices: np.ndarray) -> np.ndarray:
    """r_t = ln(P_t / P_{t-1}); length len(prices) - 1. Prices must be positive."""
    p = np.asarray(prices, dtype=np.float64)
    if (p[~np.isnan(p)] <= 0).any():
        raise ValueError("prices must be positive")
    return np.diff(np.log(p))


def reconstruct_prices(last_price: float, log_return_path: np.ndarray) -> np.ndarray:
    """Prices implied by a path of per-step log returns starting after ``last_price``.

    Note: applied to a path of per-step medians this is the *median-path* price, not the median
    of the h-step price distribution (per-step quantiles do not add up).
    """
    if last_price <= 0:
        raise ValueError("last_price must be positive")
    return float(last_price) * np.exp(np.cumsum(np.asarray(log_return_path, dtype=np.float64), axis=-1))


def logit(p: np.ndarray, eps: float = DEFAULT_EPS) -> np.ndarray:
    """z = ln(p / (1 - p)) with p clipped to [eps, 1 - eps]."""
    if not 0 < eps < 0.5:
        raise ValueError("eps must be in (0, 0.5)")
    p = np.clip(np.asarray(p, dtype=np.float64), eps, 1 - eps)
    return np.log(p) - np.log1p(-p)


def inv_logit(z: np.ndarray, eps: float = DEFAULT_EPS) -> np.ndarray:
    """Numerically stable sigmoid, clipped to [eps, 1 - eps] so outputs are strictly in (0, 1)."""
    z = np.asarray(z, dtype=np.float64)
    out = np.where(z >= 0, 1.0 / (1.0 + np.exp(-np.abs(z))), np.exp(-np.abs(z)) / (1.0 + np.exp(-np.abs(z))))
    return np.clip(out, eps, 1 - eps)
