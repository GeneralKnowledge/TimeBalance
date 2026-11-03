"""Offline stand-ins for Polymarket (an httpx transport) and Yahoo (a downloader function).

The fake Polymarket API serves payloads in the exact shapes recorded from the live APIs on
2026-11-03 (see tests/fixtures/http/), generated deterministically so tests can control them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pandas as pd

from mpe.clock import FixedClock
from mpe.config import AssetsConfig, Settings, WatchItem
from mpe.storage.database import make_engine, session_factory, upgrade

T0 = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def settings(**pm_selection) -> Settings:
    s = Settings()
    s.http.max_retries = 2
    s.http.backoff_base_s = 0.01
    s.polymarket.min_request_interval_s = 0
    sel = s.polymarket.selection
    sel.target_open, sel.target_resolved = 2, 1
    sel.min_liquidity_open, sel.min_volume_open, sel.min_volume_resolved = 1000, 1000, 1000
    for k, v in pm_selection.items():
        setattr(sel, k, v)
    return s


def db(tmp_path):
    engine = make_engine(tmp_path / "t.sqlite3")
    upgrade(engine)
    return engine, session_factory(engine)


def gamma_market(i: int, *, closed: bool = False, neg_risk: bool = False, outcomes=("Yes", "No"),
                 outcome_prices=None, uma="", days: int = 40, volume: float = 1e6, liquidity: float = 5e4,
                 description: str = "Resolves Yes if the thing happens.") -> dict:  # fmt: skip
    start = T0 - timedelta(days=days)
    end = T0 - timedelta(days=2) if closed else T0 + timedelta(days=60)
    return {
        "id": str(1000 + i),
        "question": f"Test market {i}?",
        "conditionId": f"0x{i:064x}",
        "slug": f"test-market-{i}",
        "description": description,
        "outcomes": json.dumps(list(outcomes)),
        "outcomePrices": json.dumps(outcome_prices or (["1", "0"] if closed else ["0.4", "0.6"])),
        "clobTokenIds": json.dumps([f"{i}1", f"{i}2"][: len(outcomes)]),
        "negRisk": neg_risk,
        "active": True,
        "closed": closed,
        "closedTime": (end + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S+00") if closed else None,
        "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "umaResolutionStatus": uma or ("resolved" if closed else None),
        "liquidityNum": None if closed else liquidity,
        "volumeNum": volume,
        "feesEnabled": True,
        "feeSchedule": {"exponent": 1, "rate": 0.04, "takerOnly": True, "rebateRate": 0.25},
        "events": [{"id": str(500 + i), "slug": f"event-{i}"}],
    }


class FakePolymarket:
    """Serves Gamma / CLOB / Data API v2 routes. ``fail`` lets a test inject failures per route."""

    def __init__(self, open_markets: list[dict], closed_markets: list[dict], clock: FixedClock):
        self.open = open_markets
        self.closed = closed_markets
        self.clock = clock
        self.price_shift = 0.0  # change served prices to simulate a source correction
        self.fail: dict[str, Callable[[httpx.Request], httpx.Response]] = {}
        self.calls: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def price(self, token: str, t: int) -> float:
        base = 0.3 + (int(token) % 7) * 0.05
        return round(min(max(base + 0.1 * np.sin(t / 36000.0) + self.price_shift, 0.001), 0.999), 3)

    def handle(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        self.calls.append(path)
        for key, fn in self.fail.items():
            if key in path:
                return fn(req)
        q = dict(req.url.params)
        if path == "/markets/keyset":
            if "condition_ids" in q:
                ids = set(req.url.params.get_list("condition_ids"))
                ms = [m for m in self.open + self.closed if m["conditionId"] in ids]
            else:
                ms = self.closed if q.get("closed") == "true" else self.open
            return httpx.Response(200, json={"markets": ms, "next_cursor": None})
        if path == "/prices-history":
            a, b = int(q["startTs"]), int(q["endTs"])
            if b - a > 15 * 86400:
                return httpx.Response(
                    400, json={"error": "invalid filters: 'startTs' and 'endTs' interval is too long"}
                )
            first = (a // 3600 + 1) * 3600 + 17
            hist = [{"t": t, "p": self.price(q["market"], t)} for t in range(first, b, 3600)]
            return httpx.Response(200, json={"history": hist})
        if path == "/book":
            tok = q["token_id"]
            p = self.price(tok, int(self.clock.now().timestamp()))
            bids = [{"price": f"{p - 0.01 * k:.2f}", "size": "100"} for k in range(3, 0, -1)]  # worst first
            asks = [{"price": f"{p + 0.01 * k:.2f}", "size": "150"} for k in range(3, 0, -1)]
            ts = str(int(self.clock.now().timestamp() * 1000))
            return httpx.Response(
                200, json={"market": "0x", "asset_id": tok, "timestamp": ts, "bids": bids, "asks": asks}
            )
        if path == "/v2/resolutions":
            cids = q["condition"].split(",")
            rows = [
                {
                    "condition_id": c,
                    "status": "resolved",
                    "last_update_timestamp": str(int((T0 - timedelta(days=1)).timestamp())),
                }
                for c in cids
            ]
            return httpx.Response(200, json={"data": rows})
        if path == "/v2/trades":
            cid = q["condition"]
            m = next(m for m in self.open + self.closed if m["conditionId"] == cid)
            toks = json.loads(m["clobTokenIds"])
            now = int(self.clock.now().timestamp())
            rows = [{"token_id": toks[k % 2], "timestamp": now - 600 * k, "size": 10.0 + k, "price": 0.5,
                     "side": "BUY", "condition_id": cid} for k in range(40)]  # fmt: skip
            return httpx.Response(200, json={"data": rows, "pagination": {"next_cursor": None}})
        return httpx.Response(404, json={"error": f"no route {path}"})


def yahoo_frame(symbol: str, start: datetime, end: datetime, shift: float = 0.0) -> pd.DataFrame:
    """Daily bars on NYSE sessions (FX on weekdays), labelled like yfinance (local midnight)."""
    import exchange_calendars as xc

    if symbol.endswith("=X"):
        days = pd.bdate_range(start.date(), end.date())
        idx = pd.DatetimeIndex([pd.Timestamp(d, tz="Europe/London") for d in days])
    else:
        cal = xc.get_calendar("XNYS", start="2000-01-01")
        days = cal.sessions_in_range(pd.Timestamp(start.date()), pd.Timestamp(end.date()))
        idx = pd.DatetimeIndex([pd.Timestamp(d.date(), tz="America/New_York") for d in days])
    n = len(idx)
    day = np.array([(d.date() - datetime(2000, 1, 1).date()).days for d in idx])
    base = 100 + day * 0.01 + shift  # a function of the date, so any window gives the same bar
    return pd.DataFrame(
        {"Open": base, "High": base + 1, "Low": base - 1, "Close": base + 0.5, "Adj Close": base + 0.4,
         "Volume": np.full(n, 1_000_000), "Dividends": np.zeros(n), "Stock Splits": np.zeros(n)},
        index=idx,
    )  # fmt: skip


def small_assets() -> AssetsConfig:
    return AssetsConfig(
        watchlist=[WatchItem(symbol="SPY", asset_type="etf"), WatchItem(symbol="AAPL", asset_type="stock")],
        fx=[WatchItem(symbol="GBPUSD=X", asset_type="fx")],
    )
