"""Target transforms: log returns for prices, logit for prediction-market YES prices."""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_EPS = 1e-4

# Initial stock forecasting uses the ordinary (split-adjusted) close. ``adj_close`` folds in
# dividends retrospectively, which a simulated forecast could not have known; it stays stored but
# is not a forecasting input until a dividend policy exists (docs/KNOWN_LIMITATIONS.md).
STOCK_PRICE_FIELD = "close"
PRICE_FIELDS = ("close", "adj_close")


class MissingPriceError(ValueError):
    """A bar has no value in the selected price field; there is deliberately no fallback."""


def price_series(history: pd.DataFrame, field: str = STOCK_PRICE_FIELD) -> pd.Series:
    """The selected price field of a history frame as float64, indexed by timestamp.

    ``field`` is explicit and never substituted: a missing ``close`` raises rather than borrowing
    ``adj_close`` (or vice versa).
    """
    if field not in PRICE_FIELDS:
        raise ValueError(f"unknown price field {field!r}; expected one of {PRICE_FIELDS}")
    if field not in history.columns:
        raise MissingPriceError(f"history has no {field!r} column")
    col = history[field]
    missing = col.isna()
    if missing.any():
        first = history.loc[missing, "timestamp"].iloc[0] if "timestamp" in history else None
        raise MissingPriceError(f"{int(missing.sum())} bars have no {field!r} (first: {first})")
    idx = pd.DatetimeIndex(history["timestamp"]) if "timestamp" in history else history.index
    out = pd.Series(col.astype("float64").to_numpy(), index=idx, name=field)
    return out


def stock_log_returns(history: pd.DataFrame, field: str = STOCK_PRICE_FIELD) -> pd.Series:
    """Daily log returns of ``field`` (default ``close``), labelled by the later bar's timestamp."""
    p = price_series(history, field)
    return pd.Series(log_returns(p.to_numpy()), index=p.index[1:], name=f"log_return_{field}")


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
