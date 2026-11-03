"""Initial stock forecasting reads ``close``, never ``adj_close`` (no retrospective dividend leak)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from tests.fakes import db

from mpe.data.providers.base import Instrument, ObservationRecord
from mpe.features.transforms import (
    STOCK_PRICE_FIELD,
    MissingPriceError,
    price_series,
    reconstruct_prices,
    stock_log_returns,
)
from mpe.storage import repositories as R
from mpe.storage.orm import Observation
from mpe.storage.replay import get_reconstructed_history

T = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)
CLOSE = ["100", "102", "101", "103"]
ADJ = ["95", "97.5", "96", "103"]  # dividend-adjusted after the fact: differs before the ex-date


def frame():
    return pd.DataFrame({
        "timestamp": pd.to_datetime([T + timedelta(days=i) for i in range(4)], utc=True),
        "close": [Decimal(c) for c in CLOSE], "adj_close": [Decimal(a) for a in ADJ],
    })  # fmt: skip


def test_default_price_field_is_close():
    assert STOCK_PRICE_FIELD == "close"
    p = price_series(frame())
    assert p.name == "close" and list(p) == [100.0, 102.0, 101.0, 103.0]


def test_log_returns_use_close_and_reconstruct_prices():
    r = stock_log_returns(frame())
    expected = np.diff(np.log([100.0, 102.0, 101.0, 103.0]))
    np.testing.assert_allclose(r.to_numpy(), expected)
    assert r.name == "log_return_close" and r.index[0] == pd.Timestamp(T + timedelta(days=1))
    adj = np.diff(np.log([95.0, 97.5, 96.0, 103.0]))
    assert not np.allclose(r.to_numpy(), adj)  # really not the adjusted series
    np.testing.assert_allclose(reconstruct_prices(100.0, r.to_numpy()), [102.0, 101.0, 103.0])


def test_missing_close_raises_and_never_falls_back_to_adj_close():
    df = frame()
    df.loc[2, "close"] = None
    with pytest.raises(MissingPriceError, match="'close'"):
        stock_log_returns(df)
    with pytest.raises(MissingPriceError):
        price_series(df.drop(columns=["close"]))
    with pytest.raises(ValueError, match="unknown price field"):
        price_series(df, field="Adj Close")


def test_adjusted_close_is_still_stored_and_selectable_explicitly(tmp_path):
    _, factory = db(tmp_path)
    with factory() as s:
        a = R.get_or_create_asset(s, Instrument("SPY", "yfinance", "etf"))
        recs = [ObservationRecord(symbol="SPY", timestamp=T + timedelta(days=i), interval="1d", source="yfinance",
                                  retrieved_at=T + timedelta(days=i, hours=1),
                                  available_at=T + timedelta(days=i, minutes=30),
                                  close=Decimal(c), adj_close=Decimal(j)) for i, (c, j) in enumerate(zip(CLOSE, ADJ, strict=True))]  # fmt: skip
        R.write_observations(s, a.id, recs)
        s.commit()
        assert [o.adj_close for o in s.query(Observation).order_by(Observation.timestamp)] == [
            Decimal(x) for x in ADJ
        ]
        as_of = T + timedelta(days=5)
        for h in (R.get_history(s, a.id, as_of, "1d"), get_reconstructed_history(s, a.id, as_of, "1d")):
            assert list(price_series(h)) == [float(c) for c in CLOSE]
            assert list(price_series(h, field="adj_close")) == [float(x) for x in ADJ]


def test_yahoo_provider_keeps_close_and_adj_close_separate():
    from tests.fakes import settings, small_assets

    from mpe.clock import FixedClock
    from mpe.data.providers.yahoo import YahooProvider

    clock = FixedClock(datetime(2024, 1, 10, tzinfo=UTC))
    df = pd.DataFrame({"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Adj Close": [1.25],
                       "Volume": [10]}, index=pd.DatetimeIndex([pd.Timestamp("2024-01-02")]))  # fmt: skip
    yp = YahooProvider(settings(), small_assets(), clock, downloader=lambda *a: df)
    (rec,) = yp.to_records(Instrument("SPY", "yfinance", "etf"), df)
    assert (rec.close, rec.adj_close) == (Decimal("1.5"), Decimal("1.25"))
