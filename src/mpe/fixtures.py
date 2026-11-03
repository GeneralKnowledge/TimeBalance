"""Loaders for the small committed offline fixtures in tests/fixtures/ (used by tests and M0 scripts)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from mpe.models.base import ForecastInput

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def spy_daily() -> pd.DataFrame:
    """~1,500 SPY daily bars (Yahoo chart API; timestamp = session open in UTC)."""
    df = pd.read_csv(FIXTURES / "spy_daily.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def pm_yes_hourly() -> pd.DataFrame:
    """1,500 hourly YES prices, Polymarket 'Will Donald Trump win the 2024 US Presidential Election?'."""
    df = pd.read_csv(FIXTURES / "pm_yes_hourly.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def sine_noise() -> pd.DataFrame:
    """Synthetic 10*sin(2*pi*t/24) + 0.01*t + N(0, 0.5) noise, with the noiseless answer."""
    return pd.read_csv(FIXTURES / "sine_noise.csv")


def make_input(
    values: np.ndarray,
    timestamps: pd.DatetimeIndex | pd.Series,
    horizon: int,
    names: tuple[str, ...] = ("y",),
    step: pd.Timedelta | None = None,
    **kw,
) -> ForecastInput:
    """Build a ForecastInput whose cutoff is the last context timestamp.

    Future timestamps step forward by ``step`` (default: the median spacing). M0 uses this
    simple calendar; trading-calendar-aware targets arrive with the data layer in M1.
    """
    ts = pd.DatetimeIndex(timestamps)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    step = step if step is not None else pd.Series(ts).diff().median()
    future = pd.DatetimeIndex([ts[-1] + step * (k + 1) for k in range(horizon)])
    cutoff = ts[-1].to_pydatetime().astimezone(UTC)
    return ForecastInput(
        values=np.asarray(values, dtype=np.float64),
        timestamps=ts.tz_convert(None).to_numpy(),
        series_names=names,
        horizon=horizon,
        input_cutoff=cutoff,
        future_timestamps=future.tz_convert(None).to_numpy(),
        **kw,
    )


def synthetic_index(n: int, start: str = "2020-01-01", freq: str = "h") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq=freq, tz="UTC")


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)
