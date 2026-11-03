from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from tests.fakes import settings, small_assets, yahoo_frame

from mpe.clock import FixedClock
from mpe.data.providers.base import Instrument, ProviderError
from mpe.data.providers.yahoo import YahooProvider

SPY = Instrument("SPY", "yfinance", "etf")
FX = Instrument("GBPUSD=X", "yfinance", "fx")


def prov(clock, downloader):
    return YahooProvider(settings(), small_assets(), clock, downloader=downloader)


def test_daily_bar_timestamp_is_session_close_including_early_close_and_dst():
    clock = FixedClock(datetime(2025, 12, 5, 12, tzinfo=UTC))
    p = prov(clock, lambda s, a, b: yahoo_frame(s, a, b))
    recs = {
        r.timestamp.date().isoformat(): r
        for r in p.fetch_history(SPY, datetime(2025, 10, 30, tzinfo=UTC), clock.now())
    }
    assert recs["2025-10-31"].timestamp == datetime(2025, 10, 31, 20, 0, tzinfo=UTC)  # EDT close
    assert recs["2025-11-03"].timestamp == datetime(2025, 11, 3, 21, 0, tzinfo=UTC)  # EST close
    assert recs["2025-11-28"].timestamp == datetime(
        2025, 11, 28, 18, 0, tzinfo=UTC
    )  # day after Thanksgiving, 13:00 ET
    assert recs["2025-11-28"].available_at == datetime(2025, 11, 28, 18, 30, tzinfo=UTC)
    assert "2025-11-27" not in recs  # Thanksgiving


def test_forming_bar_is_dropped_and_fx_bar_ends_at_london_midnight():
    clock = FixedClock(datetime(2026, 11, 3, 20, 45, tzinfo=UTC))  # NYSE still open (closes 21:00Z)
    p = prov(clock, lambda s, a, b: yahoo_frame(s, a, b))
    spy = p.fetch_history(SPY, datetime(2026, 10, 26, tzinfo=UTC), clock.now())
    assert spy[-1].timestamp == datetime(2026, 11, 2, 21, 0, tzinfo=UTC)
    fx = p.fetch_history(FX, datetime(2026, 10, 26, tzinfo=UTC), clock.now())
    assert fx[-1].timestamp == datetime(2026, 11, 3, 0, 0, tzinfo=UTC)  # the 2 Nov London bar
    assert all(r.available_at <= clock.now() for r in spy + fx)


def test_float32_noise_rounded_dividends_flagged_nan_rows_skipped():
    clock = FixedClock(datetime(2026, 1, 10, tzinfo=UTC))

    def dl(s, a, b):
        df = yahoo_frame(s, a, b)
        df.iloc[0, df.columns.get_loc("Close")] = np.float32(768.79).item()
        df.iloc[1, df.columns.get_loc("Dividends")] = 1.25
        df.iloc[2, :] = np.nan
        return df

    recs = prov(clock, dl).fetch_history(SPY, datetime(2026, 1, 2, tzinfo=UTC), clock.now())
    assert recs[0].close == Decimal("768.79")
    assert recs[1].quality_flags == ("dividend:1.25",)
    assert len(recs) == len(yahoo_frame("SPY", datetime(2026, 1, 2), datetime(2026, 1, 11))) - 1


def test_download_errors_retry_then_raise():
    clock = FixedClock(datetime(2026, 1, 10, tzinfo=UTC))
    calls = []

    def dl(s, a, b):
        calls.append(1)
        raise RuntimeError("Too Many Requests")

    with pytest.raises(ProviderError):
        prov(clock, dl).fetch_history(SPY, datetime(2026, 1, 2, tzinfo=UTC), clock.now())
    assert len(calls) == 3 and len(clock.slept) == 3

    with pytest.raises(ProviderError, match="missing columns"):
        prov(
            clock,
            lambda s, a, b: pd.DataFrame(
                {"Close": [1.0]}, index=[pd.Timestamp("2026-01-05", tz="America/New_York")]
            ),
        ).fetch_history(SPY, datetime(2026, 1, 2, tzinfo=UTC), clock.now() - timedelta(days=1))
