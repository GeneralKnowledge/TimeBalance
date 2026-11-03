"""Yahoo Finance daily bars through ``yfinance`` (unofficial; personal research use only).

Normalisation (see docs/DATA_SOURCES.md):

- Stock / ETF / index bars: Yahoo labels a daily bar with the session *date*. We set
  ``timestamp`` to that session's actual close from the exchange calendar (handles early closes
  and DST) and ``available_at = close + stock_close_delay_minutes``.
- FX bars (``GBPUSD=X``): Yahoo labels them with the London calendar date; the bar is treated as
  ending at the following 00:00 Europe/London, ``available_at`` = that + ``fx_close_delay_minutes``.
- Bars whose ``available_at`` is after the retrieval time are still forming and are dropped.
- ``close`` is Yahoo's split-adjusted close (``auto_adjust=False``); ``adj_close`` also adjusts for
  dividends. Prices are rounded to the 7 significant digits Yahoo's float32 values
  carry. Dividends and splits on a bar are kept as ``quality_flags`` (``dividend:0.5``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from mpe.clock import Clock
from mpe.config import AssetsConfig, Settings
from mpe.data.providers.base import Instrument, ObservationRecord, ProviderError
from mpe.storage.types import to_decimal

log = logging.getLogger(__name__)

PROVIDER = "yfinance"
SOURCE = "yfinance"
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def _px(value):
    """Yahoo serves float32 prices (768.79 arrives as 768.7899780273438). Keep the 7 significant
    digits float32 actually carries, so stored text is the quoted price, not binary noise."""
    if value is None or pd.isna(value):
        return None
    return to_decimal(format(float(value), ".7g"))


Downloader = Callable[[str, datetime, datetime], pd.DataFrame]


def yfinance_downloader(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import yfinance as yf

    return yf.Ticker(symbol).history(
        start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="1d",
        auto_adjust=False, actions=True, raise_errors=True,
    )  # fmt: skip


class YahooProvider:
    name = PROVIDER

    def __init__(
        self,
        settings: Settings,
        assets: AssetsConfig,
        clock: Clock,
        downloader: Downloader = yfinance_downloader,
        calendar=None,
    ):
        self.settings = settings
        self.assets = assets
        self.clock = clock
        self.download = downloader
        self.stock_delay = timedelta(minutes=settings.availability.stock_close_delay_minutes)
        self.fx_delay = timedelta(minutes=settings.availability.fx_close_delay_minutes)
        self.max_retries = settings.http.max_retries
        self.backoff = settings.http.backoff_base_s
        self._calendar = calendar

    @property
    def calendar(self):
        if self._calendar is None:
            import exchange_calendars as xc

            self._calendar = xc.get_calendar(self.settings.stocks.calendar, start="2000-01-01")
        return self._calendar

    def list_instruments(self) -> Sequence[Instrument]:
        out = []
        for w in [*self.assets.watchlist, *self.assets.fx]:
            out.append(
                Instrument(symbol=w.symbol, provider=PROVIDER, asset_type=w.asset_type, name=w.name,
                           exchange=w.exchange, currency=w.currency)
            )  # fmt: skip
        return out

    def _download(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                df = self.download(symbol, start, end)
            except Exception as e:  # noqa: BLE001 - yfinance raises many types (HTTP, rate limit, parsing)
                last = e
                log.warning("yfinance %s attempt %d: %s: %s", symbol, attempt, type(e).__name__, e)
                self.clock.sleep(min(self.backoff * 2**attempt, 60))
                continue
            if df is None or not isinstance(df, pd.DataFrame):
                raise ProviderError(f"yfinance {symbol}: no DataFrame returned")
            return df
        raise ProviderError(f"yfinance {symbol}: failed after retries: {type(last).__name__}: {last}")

    def bar_close(self, instrument: Instrument, label: pd.Timestamp) -> tuple[datetime, tuple[str, ...]]:
        """UTC time at which the bar labelled ``label`` (a local date) is complete."""
        day = label.date()
        if instrument.asset_type == "fx":
            end_local = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=LONDON)
            return end_local.astimezone(ZoneInfo("UTC")), ()
        session = pd.Timestamp(day)
        cal = self.calendar
        if cal.is_session(session):
            return cal.session_close(session).to_pydatetime(), ()
        fallback = datetime.combine(day, time(16, 0), tzinfo=NEW_YORK).astimezone(ZoneInfo("UTC"))
        return fallback, ("not_a_calendar_session",)

    def to_records(self, instrument: Instrument, df: pd.DataFrame) -> list[ObservationRecord]:
        retrieved = self.clock.now()
        delay = self.fx_delay if instrument.asset_type == "fx" else self.stock_delay
        need = {"Open", "High", "Low", "Close"}
        if not df.empty and not need <= set(df.columns):
            raise ProviderError(f"yfinance {instrument.symbol}: missing columns {need - set(df.columns)}")
        out = []
        for label, row in df.iterrows():
            ts, flags = self.bar_close(instrument, pd.Timestamp(label))
            available = ts + delay
            if available > retrieved:
                continue  # bar still forming
            flags = list(flags)
            div = row.get("Dividends")
            if div is not None and pd.notna(div) and float(div) != 0:
                flags.append(f"dividend:{to_decimal(float(div))}")
            split = row.get("Stock Splits")
            if split is not None and pd.notna(split) and float(split) != 0:
                flags.append(f"split:{to_decimal(float(split))}")
            close = _px(row.get("Close"))
            if close is None:
                continue  # Yahoo emits all-NaN rows for some holidays; never store an invented bar
            vol = row.get("Volume")
            out.append(
                ObservationRecord(
                    symbol=instrument.symbol, timestamp=ts, interval="1d", source=SOURCE,
                    source_ts=None, retrieved_at=retrieved, available_at=available,
                    open=_px(row.get("Open")), high=_px(row.get("High")),
                    low=_px(row.get("Low")), close=close,
                    adj_close=_px(row.get("Adj Close")) if "Adj Close" in df.columns else None,
                    volume=to_decimal(int(vol)) if vol is not None and pd.notna(vol) else None,
                    quality_flags=tuple(flags),
                )
            )  # fmt: skip
        return out

    def fetch_history(
        self, instrument: Instrument, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[ObservationRecord]:
        if interval != "1d":
            raise ValueError("only daily bars are ingested from Yahoo")
        df = self._download(instrument.symbol, start, end + timedelta(days=1))
        return self.to_records(instrument, df)

    def fetch_latest(self, instrument: Instrument) -> ObservationRecord | None:
        now = self.clock.now()
        recs = self.fetch_history(instrument, now - timedelta(days=10), now)
        return recs[-1] if recs else None
