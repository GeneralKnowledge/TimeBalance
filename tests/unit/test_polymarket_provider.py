import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from tests.fakes import T0, FakePolymarket, gamma_market, settings

from mpe.clock import FixedClock
from mpe.data.providers.base import HttpJson, Instrument, ProviderError
from mpe.data.providers.polymarket import (
    PolymarketProvider,
    evaluate_candidate,
    parse_market,
    resolution_from_gamma,
    select_markets,
)

REC = json.loads((Path(__file__).parents[1] / "fixtures" / "http" / "gamma_markets.json").read_text())


def provider(fake: FakePolymarket, clock, **kw) -> PolymarketProvider:
    return PolymarketProvider(settings(**kw), clock, transport=fake.transport())


def test_parse_recorded_markets():
    open_ = [parse_market(m) for m in REC["open"]]
    assert all(m.neg_risk and m.is_binary for m in open_)
    ok, why = evaluate_candidate(open_[0], settings().polymarket, T0)
    assert not ok and "multi-outcome" in why
    resolved = parse_market(REC["closed"][0])  # MicroStrategy sells any Bitcoin by May 31, 2026?
    assert (resolved.resolution_status, resolved.resolution_value) == ("resolved", "NO")
    assert resolved.yes_token_id == json.loads(REC["closed"][0]["clobTokenIds"])[0]
    assert resolved.fee_bps == Decimal(400)
    assert resolved.closed_time == datetime(2026, 6, 4, 0, 34, 19, tzinfo=UTC)


@pytest.mark.parametrize(
    ("closed", "uma", "prices", "expected"),
    [
        (False, None, ["0.4", "0.6"], ("open", None)),
        (True, "resolved", ["1", "0"], ("resolved", "YES")),
        (True, "resolved", ["0", "1"], ("resolved", "NO")),
        (True, "resolved", ["0.5", "0.5"], ("resolved", "SPLIT")),
        (True, "resolved", ["0.7", "0.3"], ("ambiguous", None)),
        (True, "disputed", ["0", "1"], ("disputed", None)),
        (True, None, ["0.2", "0.8"], ("closed", None)),
    ],
)
def test_resolution_mapping(closed, uma, prices, expected):
    m = {"closed": closed, "umaResolutionStatus": uma, "outcomePrices": json.dumps(prices)}
    assert resolution_from_gamma(m) == expected


def test_selection_rules_record_reasons_and_keep_existing_panel():
    cfg = settings(target_open=1).polymarket
    ms = [
        parse_market(gamma_market(1, volume=5e6)),
        parse_market(gamma_market(2, volume=9e6)),
        parse_market(gamma_market(3, neg_risk=True)),
        parse_market(gamma_market(4, outcomes=("Spurs", "Knicks"))),
        parse_market(gamma_market(5, liquidity=10)),
        parse_market(gamma_market(6, days=3)),
        parse_market(gamma_market(7, description="")),
    ]
    out = {d.market.question: d for d in select_markets(ms, [], cfg, T0)}
    assert out["Test market 2?"].selected and not out["Test market 1?"].selected
    assert "outside top 1" in out["Test market 1?"].reason
    assert "multi-outcome" in out["Test market 3?"].reason
    assert "binary" in out["Test market 4?"].reason
    assert "liquidity" in out["Test market 5?"].reason
    assert "days of history" in out["Test market 6?"].reason
    assert "resolution rules" in out["Test market 7?"].reason
    # market 1 was chosen in an earlier run: it stays, even though market 2 now has more volume
    again = {
        d.market.question: d for d in select_markets(ms, [], cfg, T0, already_selected={ms[0].condition_id})
    }
    assert again["Test market 1?"].selected


def test_history_uses_short_windows_floors_hours_and_drops_forming_hour():
    clock = FixedClock(T0 + timedelta(minutes=30))
    fake = FakePolymarket([], [], clock)
    p = provider(fake, clock)
    inst = Instrument("11", "polymarket", "pm_token", outcome_side="YES")
    recs = p.fetch_history(inst, T0 - timedelta(days=30), clock.now())
    assert fake.calls.count("/prices-history") == 3  # 30 days in <= 14-day windows
    assert all(r.timestamp.minute == 0 and r.source_ts.minute == 0 and r.source_ts.second == 17 for r in recs)
    assert recs[-1].timestamp < T0  # the 12:00 bucket is still forming at 12:30
    assert all(r.available_at == r.source_ts + timedelta(seconds=60) for r in recs)
    assert all(Decimal(0) < r.close < Decimal(1) for r in recs)


def test_order_book_sorted_best_first_and_snapshot_flags_midpoint():
    clock = FixedClock(T0)
    p = provider(FakePolymarket([], [], clock), clock)
    book = p.fetch_order_book("11")
    assert book.bids[0][0] > book.bids[-1][0] and book.asks[0][0] < book.asks[-1][0]
    snap = p.snapshot_from_book(book)
    assert snap.bid == book.bids[0][0] and snap.ask == book.asks[0][0]
    assert snap.close == (snap.bid + snap.ask) / 2 and "close_is_midpoint" in snap.quality_flags


def test_trade_aggregation_only_complete_hours():
    clock = FixedClock(T0 + timedelta(minutes=45))
    m = gamma_market(1)
    p = provider(FakePolymarket([m], [], clock), clock)
    recs = p.fetch_hourly_trade_volume(m["conditionId"], ["11", "12"])
    assert recs and all(r.timestamp < T0 for r in recs)  # current hour excluded
    assert all(r.available_at >= r.timestamp + timedelta(hours=1) for r in recs)
    assert sum(r.trade_count for r in recs) < 40


def _client(handler, clock, **kw):
    return HttpJson("t", clock, transport=httpx.MockTransport(handler), max_retries=3, backoff_base_s=1, **kw)


def test_http_retries_429_with_retry_after_then_succeeds():
    clock = FixedClock(T0)
    calls = []

    def h(req):
        calls.append(1)
        return (
            httpx.Response(429, headers={"Retry-After": "7"})
            if len(calls) < 3
            else httpx.Response(200, json={"ok": 1})
        )

    assert _client(h, clock).get("https://x/y") == {"ok": 1}
    assert clock.slept == [7.0, 7.0]


@pytest.mark.parametrize(
    "handler",
    [
        lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=req)),
        lambda req: httpx.Response(503),
        lambda req: httpx.Response(200, content=b"{not json"),
        lambda req: httpx.Response(400, json={"error": "bad"}),
    ],
    ids=["timeout", "503", "malformed-json", "400"],
)
def test_http_failures_raise_provider_error(handler):
    clock = FixedClock(T0)
    with pytest.raises(ProviderError):
        _client(handler, clock).get("https://x/y")
    assert all(s <= 60 for s in clock.slept)
