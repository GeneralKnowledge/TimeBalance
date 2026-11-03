"""Provider abstraction: normalised records with provenance, and a polite HTTP client.

Every provider returns these records; nothing downstream sees a provider's raw format except via
``raw`` payloads kept for audit. All prices and sizes are :class:`~decimal.Decimal`; all times are
timezone-aware UTC.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

import httpx

from mpe.clock import Clock

log = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A provider call failed after retries, or returned something we cannot trust."""


class BudgetExhausted(ProviderError):
    pass


@dataclass(frozen=True)
class Instrument:
    symbol: str  # 'SPY', 'GBPUSD=X', or a Polymarket token id
    provider: str
    asset_type: str  # 'stock','etf','crypto','fx','index','pm_token'
    name: str | None = None
    exchange: str | None = None
    currency: str = "USD"
    outcome_side: str | None = None  # pm_token only
    market_key: str | None = None  # pm_token only: condition id
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationRecord:
    symbol: str
    timestamp: datetime  # bar close / snapshot time (UTC)
    interval: str  # '1d','1h','snapshot'
    source: str
    retrieved_at: datetime
    available_at: datetime
    source_ts: datetime | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    adj_close: Decimal | None = None
    volume: Decimal | None = None
    trade_count: int | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    bid_size: Decimal | None = None
    ask_size: Decimal | None = None
    liquidity: Decimal | None = None
    quality_flags: tuple[str, ...] = ()

    VALUE_FIELDS = (
        "open", "high", "low", "close", "adj_close", "volume", "trade_count",
        "bid", "ask", "bid_size", "ask_size", "liquidity",
    )  # fmt: skip

    def values(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.VALUE_FIELDS}


@dataclass(frozen=True)
class OrderBookRecord:
    token_id: str
    timestamp: datetime  # book time reported by the source
    retrieved_at: datetime
    bids: tuple[tuple[Decimal, Decimal], ...]  # best (highest) first
    asks: tuple[tuple[Decimal, Decimal], ...]  # best (lowest) first
    source: str = "polymarket_clob"
    raw: dict | None = None

    @property
    def best_bid(self) -> tuple[Decimal, Decimal] | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> tuple[Decimal, Decimal] | None:
        return self.asks[0] if self.asks else None


@dataclass(frozen=True)
class QualityIssue:
    check_name: str
    severity: str  # 'info' | 'warning' | 'error'
    details: dict
    symbol: str | None = None
    source: str | None = None


class MarketDataProvider(Protocol):
    name: str

    def list_instruments(self) -> Sequence[Instrument]: ...

    def fetch_history(
        self, instrument: Instrument, start: datetime, end: datetime, interval: str
    ) -> list[ObservationRecord]: ...

    def fetch_latest(self, instrument: Instrument) -> ObservationRecord | None: ...


class RequestBudget(Protocol):
    def consume(self, provider: str, n: int = 1) -> None:
        """Count ``n`` requests; raise :class:`BudgetExhausted` when the daily budget is spent."""


class UnlimitedBudget:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def consume(self, provider: str, n: int = 1) -> None:
        self.counts[provider] = self.counts.get(provider, 0) + n


RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 522, 524}


class HttpJson:
    """GET-only JSON client with retries, exponential backoff, Retry-After and a request budget.

    Read-only by construction: it exposes no method that sends a body.
    """

    def __init__(
        self,
        provider: str,
        clock: Clock,
        budget: RequestBudget | None = None,
        *,
        timeout_s: float = 30,
        max_retries: int = 5,
        backoff_base_s: float = 1.0,
        backoff_max_s: float = 60,
        min_interval_s: float = 0.0,
        user_agent: str = "TimeBalance-research/0.1",
        transport: httpx.BaseTransport | None = None,
        on_raw: Callable[[str, dict, Any], None] | None = None,
    ):
        self.provider = provider
        self.clock = clock
        self.budget = budget or UnlimitedBudget()
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.min_interval_s = min_interval_s
        self.on_raw = on_raw
        self._last: datetime | None = None
        self.requests = 0
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _pace(self) -> None:
        if self._last is not None and self.min_interval_s > 0:
            waited = (self.clock.now() - self._last).total_seconds()
            if waited < self.min_interval_s:
                self.clock.sleep(self.min_interval_s - waited)

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_max_s)
            except ValueError:
                pass
        return min(self.backoff_base_s * 2**attempt, self.backoff_max_s)

    def get(self, url: str, params: dict | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        last_error: str = ""
        for attempt in range(self.max_retries + 1):
            self.budget.consume(self.provider)
            self._pace()
            self._last = self.clock.now()
            self.requests += 1
            try:
                resp = self._client.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                log.warning("http %s %s attempt %d: %s", self.provider, url, attempt, last_error)
                self.clock.sleep(self._backoff(attempt, None))
                continue
            if resp.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {resp.status_code}"
                log.warning("http %s %s attempt %d: %s", self.provider, url, attempt, last_error)
                self.clock.sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                continue
            if resp.status_code >= 400:
                raise ProviderError(
                    f"{self.provider} GET {url} {params} -> HTTP {resp.status_code}: {resp.text[:300]}"
                )
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError) as e:
                raise ProviderError(f"{self.provider} GET {url}: malformed JSON ({e})") from e
            if self.on_raw is not None:
                self.on_raw(url, params, data)
            return data
        raise ProviderError(f"{self.provider} GET {url} {params}: gave up after retries ({last_error})")
