"""Polymarket, read-only and unauthenticated.

Endpoints used (checked live on 2026-11-03, see docs/DATA_SOURCES.md):

- Gamma ``GET /markets/keyset``: market discovery and metadata, cursor pagination (``after_cursor``).
- CLOB ``GET /prices-history``: hourly (``fidelity=60``) price samples per outcome token, in
  ``startTs``/``endTs`` windows of at most 14 days (longer windows are rejected with HTTP 400, and
  ``interval=max`` returns nothing for many resolved markets).
- CLOB ``GET /book``: current order book per token.
- Data API v2 ``GET /v2/resolutions`` (resolution state) and ``GET /v2/trades`` (trade feed,
  aggregated here into hourly volume). Data API v1 was retired on 2026-11-02.

No authenticated endpoint, no order endpoint, no wallet. This module only reads.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mpe.clock import Clock, from_epoch, from_iso
from mpe.config import Polymarket as PolymarketCfg
from mpe.config import Settings
from mpe.data.providers.base import (
    HttpJson,
    Instrument,
    ObservationRecord,
    OrderBookRecord,
    ProviderError,
    RequestBudget,
)
from mpe.storage.types import to_decimal

log = logging.getLogger(__name__)

PROVIDER = "polymarket"
SRC_HISTORY = "polymarket_clob_history"
SRC_BOOK = "polymarket_clob_book"
SRC_TRADES = "polymarket_data_trades"
HOUR = timedelta(hours=1)


def _json_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        out = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return out if isinstance(out, list) else []


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    if text.endswith("+00"):
        text += ":00"
    try:
        dt = from_iso(text) if ("Z" in text or "+" in text[10:]) else from_iso(text + "Z")
    except ValueError:
        return None
    return dt


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class MarketInfo:
    """A Gamma market, normalised. ``raw`` keeps the full source payload."""

    condition_id: str
    gamma_id: str
    question: str
    slug: str | None
    description: str | None
    outcomes: list[str]
    token_ids: list[str]
    yes_token_id: str | None
    no_token_id: str | None
    neg_risk: bool
    event_id: str | None
    event_slug: str | None
    category: str | None
    resolution_source: str | None
    opening_time: datetime | None
    closing_time: datetime | None
    closed_time: datetime | None
    closed: bool
    uma_status: str | None
    outcome_prices: list[str]
    liquidity: float
    volume: float
    fee_rate: Decimal | None
    resolution_status: str
    resolution_value: str | None
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def is_binary(self) -> bool:
        return [o.strip().lower() for o in self.outcomes] == ["yes", "no"] and len(self.token_ids) == 2

    @property
    def fee_bps(self) -> Decimal | None:
        """Taker fee *rate* in basis points: fee = shares × rate × p × (1 − p) (docs: Fees)."""
        return None if self.fee_rate is None else self.fee_rate * 10_000

    def history_days(self, now: datetime) -> float:
        if self.opening_time is None:
            return 0.0
        end = self.closed_time or self.closing_time or now
        end = min(end, now)
        return max((end - self.opening_time).total_seconds() / 86400, 0.0)


def resolution_from_gamma(m: dict) -> tuple[str, str | None]:
    """Map Gamma fields to the brief's ``resolution_status`` / ``resolution_value``."""
    closed = bool(m.get("closed"))
    uma = (m.get("umaResolutionStatus") or "").lower()
    prices = [_num(p) for p in _json_list(m.get("outcomePrices"))]
    if not closed:
        return ("disputed" if uma == "disputed" else "open"), None
    if uma in ("disputed",):
        return "disputed", None
    if uma == "resolved" and len(prices) == 2:
        if prices == [1.0, 0.0]:
            return "resolved", "YES"
        if prices == [0.0, 1.0]:
            return "resolved", "NO"
        if abs(prices[0] - 0.5) < 1e-9 and abs(prices[1] - 0.5) < 1e-9:
            return "resolved", "SPLIT"
        return "ambiguous", None
    return "closed", None


def parse_market(m: dict) -> MarketInfo:
    outcomes = [str(o) for o in _json_list(m.get("outcomes"))]
    tokens = [str(t) for t in _json_list(m.get("clobTokenIds"))]
    side = {o.strip().lower(): t for o, t in zip(outcomes, tokens, strict=False)}
    events = m.get("events") or []
    ev = events[0] if events else {}
    fee_rate = None
    if m.get("feesEnabled") is False:
        fee_rate = Decimal(0)
    elif isinstance(m.get("feeSchedule"), dict) and m["feeSchedule"].get("rate") is not None:
        fee_rate = to_decimal(m["feeSchedule"]["rate"])
    status, value = resolution_from_gamma(m)
    return MarketInfo(
        condition_id=str(m.get("conditionId") or ""),
        gamma_id=str(m.get("id") or ""),
        question=str(m.get("question") or ""),
        slug=m.get("slug"),
        description=m.get("description"),
        outcomes=outcomes,
        token_ids=tokens,
        yes_token_id=side.get("yes"),
        no_token_id=side.get("no"),
        neg_risk=bool(m.get("negRisk")),
        event_id=str(ev["id"]) if ev.get("id") is not None else None,
        event_slug=ev.get("slug"),
        category=m.get("category") or ev.get("category") or m.get("feeType"),
        resolution_source=m.get("resolutionSource") or None,
        opening_time=_parse_time(m.get("startDate") or m.get("createdAt")),
        closing_time=_parse_time(m.get("endDate")),
        closed_time=_parse_time(m.get("closedTime")),
        closed=bool(m.get("closed")),
        uma_status=m.get("umaResolutionStatus"),
        outcome_prices=[str(p) for p in _json_list(m.get("outcomePrices"))],
        liquidity=_num(m.get("liquidityNum") if m.get("liquidityNum") is not None else m.get("liquidity")),
        volume=_num(m.get("volumeNum") if m.get("volumeNum") is not None else m.get("volume")),
        fee_rate=fee_rate,
        resolution_status=status,
        resolution_value=value,
        raw=m,
    )


@dataclass(frozen=True)
class SelectionDecision:
    market: MarketInfo
    selected: bool
    reason: str


def evaluate_candidate(m: MarketInfo, cfg: PolymarketCfg, now: datetime) -> tuple[bool, str]:
    """Hard eligibility rules (brief M1). Returns (eligible, reason)."""
    s = cfg.selection
    if not m.is_binary:
        return False, f"excluded: not a Yes/No binary (outcomes={m.outcomes})"
    if not m.condition_id or not m.yes_token_id or not m.no_token_id:
        return False, "excluded: missing condition id or token ids"
    if s.exclude_neg_risk and m.neg_risk:
        return False, "excluded: leg of a multi-outcome (negRisk) event"
    if not (m.description or "").strip():
        return False, "excluded: no resolution rules in description"
    if m.resolution_status in ("ambiguous", "disputed"):
        return False, f"excluded: resolution {m.resolution_status}"
    days = m.history_days(now)
    if days < s.min_history_days:
        return False, f"excluded: only {days:.1f} days of history (< {s.min_history_days})"
    if m.closed:
        if m.resolution_status != "resolved":
            return False, f"excluded: closed but not cleanly resolved ({m.uma_status})"
        if m.volume < s.min_volume_resolved:
            return False, f"excluded: lifetime volume {m.volume:,.0f} < {s.min_volume_resolved:,.0f}"
        return True, f"eligible: resolved {m.resolution_value}, volume {m.volume:,.0f}, {days:.0f}d history"
    if m.liquidity < s.min_liquidity_open:
        return False, f"excluded: liquidity {m.liquidity:,.0f} < {s.min_liquidity_open:,.0f}"
    if m.volume < s.min_volume_open:
        return False, f"excluded: volume {m.volume:,.0f} < {s.min_volume_open:,.0f}"
    return True, f"eligible: open, liquidity {m.liquidity:,.0f}, volume {m.volume:,.0f}, {days:.0f}d history"


def select_markets(
    open_markets: Sequence[MarketInfo],
    resolved_markets: Sequence[MarketInfo],
    cfg: PolymarketCfg,
    now: datetime,
    already_selected: set[str] = frozenset(),
) -> list[SelectionDecision]:
    """Rank eligible markets by volume and keep the configured number of each kind.

    Markets already selected in an earlier run stay selected (the panel must not churn, or
    history would be survivorship-biased towards whatever is popular today).
    """
    out: list[SelectionDecision] = []
    for pool, target in (
        (open_markets, cfg.selection.target_open),
        (resolved_markets, cfg.selection.target_resolved),
    ):
        eligible: list[tuple[MarketInfo, str]] = []
        seen: set[str] = set()
        for m in pool:
            if m.condition_id in seen:
                continue
            seen.add(m.condition_id)
            ok, reason = evaluate_candidate(m, cfg, now)
            if ok:
                eligible.append((m, reason))
            else:
                out.append(SelectionDecision(m, m.condition_id in already_selected, reason))
        eligible.sort(key=lambda mr: (mr[0].condition_id not in already_selected, -mr[0].volume))
        for rank, (m, reason) in enumerate(eligible):
            keep = rank < target or m.condition_id in already_selected
            why = (
                f"selected: {reason.removeprefix('eligible: ')}"
                if keep
                else (
                    f"excluded: eligible but outside top {target} by volume ({reason.removeprefix('eligible: ')})"
                )
            )
            out.append(SelectionDecision(m, keep, why))
    return out


def token_instruments(m: MarketInfo) -> list[Instrument]:
    out = []
    for side, tok in (("YES", m.yes_token_id), ("NO", m.no_token_id)):
        if tok:
            out.append(
                Instrument(
                    symbol=tok, provider=PROVIDER, asset_type="pm_token",
                    name=f"{m.question} [{side}]", currency="USD", outcome_side=side,
                    market_key=m.condition_id,
                )
            )  # fmt: skip
    return out


def floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


class PolymarketProvider:
    name = PROVIDER

    def __init__(
        self,
        settings: Settings,
        clock: Clock,
        budget: RequestBudget | None = None,
        transport=None,
        on_raw=None,
    ):
        self.cfg = settings.polymarket
        self.latency = timedelta(seconds=settings.availability.polymarket_history_latency_seconds)
        self.clock = clock
        h = settings.http
        self.http = HttpJson(
            PROVIDER, clock, budget, timeout_s=h.timeout_s, max_retries=h.max_retries,
            backoff_base_s=h.backoff_base_s, backoff_max_s=h.backoff_max_s,
            min_interval_s=self.cfg.min_request_interval_s, user_agent=h.user_agent,
            transport=transport, on_raw=on_raw,
        )  # fmt: skip

    def close(self) -> None:
        self.http.close()

    # ---------------------------------------------------------------- discovery (Gamma)
    def iter_markets(self, *, closed: bool | str, max_markets: int, **filters) -> Iterator[dict]:
        closed = closed if isinstance(closed, str) else ("true" if closed else "false")
        params = {"limit": 100, "closed": closed, "order": "volumeNum",
                  "ascending": "false", **filters}  # fmt: skip
        n = 0
        cursor = None
        while n < max_markets:
            page = self.http.get(f"{self.cfg.gamma_url}/markets/keyset", {**params, "after_cursor": cursor})
            if not isinstance(page, dict) or not isinstance(page.get("markets"), list):
                raise ProviderError(f"gamma keyset: unexpected payload shape {type(page).__name__}")
            for m in page["markets"]:
                if not isinstance(m, dict):
                    raise ProviderError("gamma keyset: market entry is not an object")
                yield m
                n += 1
                if n >= max_markets:
                    return
            cursor = page.get("next_cursor")
            if not cursor or not page["markets"]:
                return

    def discover(self) -> tuple[list[MarketInfo], list[MarketInfo]]:
        """Candidate open markets and recently resolved ones, highest volume first."""
        s = self.cfg.selection
        now = self.clock.now()
        open_ = [
            parse_market(m) for m in self.iter_markets(closed=False, max_markets=s.max_candidates_per_scan)
        ]
        since = (now - timedelta(days=s.resolved_lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        closed = [
            parse_market(m)
            for m in self.iter_markets(closed=True, max_markets=s.max_candidates_per_scan, end_date_min=since)
        ]
        return open_, closed

    def fetch_markets_by_condition(self, condition_ids: Sequence[str]) -> list[MarketInfo]:
        out: list[MarketInfo] = []
        for i in range(0, len(condition_ids), 20):
            chunk = list(condition_ids[i : i + 20])
            for m in self.iter_markets(closed="any", max_markets=len(chunk), condition_ids=chunk):
                out.append(parse_market(m))
        return out

    # ---------------------------------------------------------------- history (CLOB)
    def fetch_history(
        self, instrument: Instrument, start: datetime, end: datetime, interval: str = "1h"
    ) -> list[ObservationRecord]:
        if interval != "1h":
            raise ValueError("Polymarket history is stored at 1h (CLOB fidelity=60)")
        retrieved = self.clock.now()
        end = min(end, retrieved)
        window = timedelta(days=self.cfg.history_window_days)
        by_hour: dict[datetime, tuple[datetime, Decimal]] = {}
        t = start
        while t < end:
            t2 = min(t + window, end)
            data = self.http.get(
                f"{self.cfg.clob_url}/prices-history",
                {"market": instrument.symbol, "startTs": int(t.timestamp()), "endTs": int(t2.timestamp()),
                 "fidelity": 60},
            )  # fmt: skip
            hist = data.get("history") if isinstance(data, dict) else None
            if not isinstance(hist, list):
                raise ProviderError("clob prices-history: missing 'history' list")
            for pt in hist:
                try:
                    ts = from_epoch(int(pt["t"]))
                    p = to_decimal(pt["p"])
                except (KeyError, TypeError, ValueError) as e:
                    raise ProviderError(f"clob prices-history: malformed point {pt!r}") from e
                if p is None:
                    continue
                bucket = floor_hour(ts)
                prev = by_hour.get(bucket)
                if prev is None or ts >= prev[0]:
                    by_hour[bucket] = (ts, p)  # latest sample within the hour wins
            t = t2
        out = []
        current = floor_hour(retrieved)
        for bucket in sorted(by_hour):
            if bucket >= current:
                continue  # the current hour is still forming; its last sample may change
            ts, p = by_hour[bucket]
            flags = () if Decimal(0) <= p <= Decimal(1) else ("price_out_of_range",)
            out.append(
                ObservationRecord(
                    symbol=instrument.symbol, timestamp=bucket, interval="1h", source=SRC_HISTORY,
                    source_ts=ts, retrieved_at=retrieved, available_at=min(ts + self.latency, retrieved), close=p,
                    quality_flags=flags,
                )
            )  # fmt: skip
        return out

    # ---------------------------------------------------------------- live book (CLOB)
    def fetch_order_book(self, token_id: str) -> OrderBookRecord:
        data = self.http.get(f"{self.cfg.clob_url}/book", {"token_id": token_id})
        retrieved = self.clock.now()
        if not isinstance(data, dict) or "bids" not in data or "asks" not in data:
            raise ProviderError("clob book: missing bids/asks")

        def levels(rows, reverse: bool):
            out = []
            for r in rows or []:
                price, size = to_decimal(r.get("price")), to_decimal(r.get("size"))
                if price is None or size is None:
                    raise ProviderError(f"clob book: malformed level {r!r}")
                out.append((price, size))
            return tuple(sorted(out, key=lambda x: x[0], reverse=reverse))

        ts_ms = data.get("timestamp")
        ts = from_epoch(int(ts_ms) / 1000) if ts_ms else retrieved
        return OrderBookRecord(
            token_id=token_id, timestamp=ts, retrieved_at=retrieved,
            bids=levels(data["bids"], reverse=True), asks=levels(data["asks"], reverse=False), raw=data,
        )  # fmt: skip

    def snapshot_from_book(
        self, book: OrderBookRecord, liquidity: Decimal | None = None
    ) -> ObservationRecord:
        bb, ba = book.best_bid, book.best_ask
        flags: list[str] = []
        mid = None
        if bb and ba:
            mid = (bb[0] + ba[0]) / 2
            flags.append("close_is_midpoint")
            if ba[0] < bb[0]:
                flags.append("crossed_book")
        else:
            flags.append("one_sided_book" if (bb or ba) else "empty_book")
        return ObservationRecord(
            symbol=book.token_id, timestamp=book.retrieved_at, interval="snapshot", source=SRC_BOOK,
            source_ts=book.timestamp, retrieved_at=book.retrieved_at, available_at=book.retrieved_at,
            close=mid, bid=bb[0] if bb else None, bid_size=bb[1] if bb else None,
            ask=ba[0] if ba else None, ask_size=ba[1] if ba else None, liquidity=liquidity,
            quality_flags=tuple(flags),
        )  # fmt: skip

    def fetch_latest(self, instrument: Instrument) -> ObservationRecord | None:
        return self.snapshot_from_book(self.fetch_order_book(instrument.symbol))

    # ---------------------------------------------------------------- resolution and trades (Data API v2)
    def fetch_resolutions(self, condition_ids: Sequence[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(condition_ids), 20):
            chunk = ",".join(condition_ids[i : i + 20])
            data = self.http.get(f"{self.cfg.data_url}/v2/resolutions", {"condition": chunk})
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ProviderError("data v2 resolutions: missing 'data' list")
            for r in rows:
                if isinstance(r, dict) and r.get("condition_id"):
                    out[r["condition_id"]] = r
        return out

    def fetch_hourly_trade_volume(
        self, condition_id: str, token_ids: Sequence[str], max_pages: int | None = None
    ) -> list[ObservationRecord]:
        """Aggregate the Data API v2 trade feed (taker side only, so each fill counts once) into
        complete hourly buckets per token. Volume is in shares. Only hours known to be complete
        are emitted: not the current hour, and not the oldest hour if pagination stopped early."""
        max_pages = max_pages or self.cfg.trades.max_pages_per_market
        retrieved = self.clock.now()
        wanted = set(token_ids)
        vol: dict[tuple[str, datetime], Decimal] = defaultdict(Decimal)
        cnt: dict[tuple[str, datetime], int] = defaultdict(int)
        oldest: datetime | None = None
        exhausted = False
        cursor = None
        for _ in range(max_pages):
            params = {"condition": condition_id, "limit": 1000} if cursor is None else {
                "condition": condition_id, "cursor": cursor}  # fmt: skip
            data = self.http.get(f"{self.cfg.data_url}/v2/trades", params)
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ProviderError("data v2 trades: missing 'data' list")
            for r in rows:
                try:
                    tok, ts, size = str(r["token_id"]), from_epoch(int(r["timestamp"])), to_decimal(r["size"])
                except (KeyError, TypeError, ValueError) as e:
                    raise ProviderError(f"data v2 trades: malformed row keys={list(r)[:8]}") from e
                oldest = ts if oldest is None or ts < oldest else oldest
                if tok in wanted and size is not None:
                    key = (tok, floor_hour(ts))
                    vol[key] += size
                    cnt[key] += 1
            cursor = (data.get("pagination") or {}).get("next_cursor")
            if not cursor:
                exhausted = True
                break
        current = floor_hour(retrieved)
        cut = None if exhausted or oldest is None else floor_hour(oldest)
        out = []
        for (tok, hour), v in sorted(vol.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            if hour >= current or (cut is not None and hour <= cut):
                continue
            out.append(
                ObservationRecord(
                    symbol=tok, timestamp=hour, interval="1h", source=SRC_TRADES, retrieved_at=retrieved,
                    available_at=min(hour + HOUR + self.latency, retrieved), volume=v, trade_count=cnt[(tok, hour)],
                )
            )  # fmt: skip
        return out


def resolved_at(m: MarketInfo, res: dict | None) -> datetime:
    if res and res.get("last_update_timestamp"):
        try:
            return from_epoch(int(res["last_update_timestamp"]))
        except (TypeError, ValueError):
            pass
    return m.closed_time or m.closing_time or datetime(1970, 1, 1, tzinfo=UTC)
