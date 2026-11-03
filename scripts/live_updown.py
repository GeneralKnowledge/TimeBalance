"""Paper-only live test: Timestral vs Polymarket on 15-minute crypto "Up or Down" markets.

`predict`: for each asset's current 15-minute window, forecast log(price / window-open price) to the
window end from Binance 1-minute closes with Timestral, turn the final-step quantiles into P(Up), and
log it next to the market's own mid price and a zero-drift random-walk baseline.
`score`: fill in outcomes of finished windows from Polymarket and print Brier / log loss / accuracy.

Caveat: Polymarket resolves on the Chainlink BTC/USD (etc.) stream, not Binance, so our strike is an
approximation of the official one. No orders are ever placed.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from mpe.models.base import ForecastInput
from mpe.models.timestral import TimestralModel

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "live_predictions.sqlite3"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
BINANCE = "https://api.binance.com/api/v3/klines"
ASSETS = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT"}
WINDOW = 900
CONTEXT_MIN = 512
LEVELS = (0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)

SCHEMA = """
create table if not exists predictions (
  id integer primary key, created_at text, slug text, asset text, window_start text, window_end text,
  minutes_left integer, strike real, last_price real, model text,
  p_up_model real, p_up_rw real, p_up_market real, quantiles text,
  outcome integer, scored_at text, binance_up integer, price_to_beat real, unique(slug, created_at))
"""

http = httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0 TimeBalance-paper"})


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute(SCHEMA)
    return c


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def gamma_market(slug: str) -> dict | None:
    rows = http.get(f"{GAMMA}/markets", params={"slug": slug}).json()
    return rows[0] if rows else None


def klines(symbol: str, end_ms: int, n: int) -> np.ndarray:
    """Completed 1-minute candles ending at or before end_ms: rows of (open_ms, open, close)."""
    raw = http.get(BINANCE, params={"symbol": symbol, "interval": "1m", "endTime": end_ms, "limit": n}).json()
    rows = [(int(k[0]), float(k[1]), float(k[4])) for k in raw if int(k[6]) < end_ms]
    return np.array(rows)


def cdf_at(x: float, q: np.ndarray, levels) -> float:
    """F(x) from quantiles by linear interpolation; clamped to the outermost levels."""
    q = np.maximum.accumulate(q)
    return float(np.interp(x, q, levels))


def predict(size: str) -> None:
    now = time.time()
    start = int(now // WINDOW * WINDOW)
    end = start + WINDOW
    model = TimestralModel(size)
    model.load("cpu")
    con = db()
    created = iso(now)
    for asset, symbol in ASSETS.items():
        slug = f"{asset}-updown-15m-{start}"
        m = gamma_market(slug)
        if not m or m.get("closed"):
            print(f"{slug}: no open market")
            continue
        k = klines(symbol, int(now * 1000), CONTEXT_MIN)
        in_window = k[k[:, 0] >= start * 1000]
        if len(in_window) == 0:
            print(f"{slug}: window just opened, no completed minute yet")
            continue
        strike = in_window[0, 1]  # Binance open at the window start (proxy for Chainlink)
        last_close_ts = k[-1, 0] / 1000 + 60
        h = int(round((end - last_close_ts) / 60))
        if h < 1:
            print(f"{slug}: under a minute left, skipped")
            continue
        y = np.log(k[:, 2] / strike)
        ts = (k[:, 0] / 1000 + 60).astype("datetime64[s]")
        fut = np.array([ts[-1] + np.timedelta64(60 * (i + 1), "s") for i in range(h)])
        out = model.forecast(ForecastInput(
            values=y, timestamps=ts, series_names=[asset], horizon=h,
            input_cutoff=datetime.fromtimestamp(last_close_ts, UTC), future_timestamps=fut,
            quantile_levels=LEVELS,
        ))  # fmt: skip
        qf = np.asarray(out.quantiles)[0, -1]  # final-step quantiles of log(P_end / strike)
        p_model = 1 - cdf_at(0.0, qf, LEVELS)
        r = np.diff(np.log(k[-61:, 2]))
        sigma = r.std(ddof=1) * math.sqrt(h)
        p_rw = 1 - 0.5 * (1 + math.erf((0 - y[-1]) / (sigma * math.sqrt(2)))) if sigma > 0 else float(y[-1] > 0)
        up_token = json.loads(m["clobTokenIds"])[0]
        mid = http.get(f"{CLOB}/midpoint", params={"token_id": up_token}).json().get("mid")
        p_mkt = float(mid) if mid is not None else None
        con.execute(
            "insert or ignore into predictions (created_at, slug, asset, window_start, window_end, minutes_left,"
            " strike, last_price, model, p_up_model, p_up_rw, p_up_market, quantiles) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (created, slug, asset, iso(start), iso(end), h, strike, float(k[-1, 2]), out.model.name,
             p_model, p_rw, p_mkt, json.dumps([round(float(v), 7) for v in qf])),
        )  # fmt: skip
        con.commit()
        print(f"{m['question']}: {h} min left, price {k[-1, 2]:.4g} vs open {strike:.4g} | "
              f"P(Up) Timestral {p_model:.3f}, random walk {p_rw:.3f}, market {p_mkt}")  # fmt: skip


def score() -> None:
    con = db()
    now = time.time()
    pending = con.execute("select distinct slug, window_end from predictions where outcome is null").fetchall()
    for slug, wend in pending:
        if datetime.fromisoformat(wend.replace("Z", "+00:00")).timestamp() > now:
            continue
        m = gamma_market(slug)
        prices = json.loads(m.get("outcomePrices") or "[]") if m else []
        if m and m.get("closed") and prices and {float(p) for p in prices} <= {0.0, 1.0}:
            # Diagnostic: did Binance (our input source) move the same way as the official result?
            asset = slug.split("-")[0]
            start_s = int(slug.rsplit("-", 1)[1])
            k = klines(ASSETS[asset], (start_s + WINDOW) * 1000, 15)
            k = k[k[:, 0] >= start_s * 1000]
            b_up = int(k[-1, 2] > k[0, 1]) if len(k) == 15 else None
            ev = http.get(f"{GAMMA}/events", params={"slug": slug}).json()
            ptb = ((ev[0].get("eventMetadata") or {}).get("priceToBeat")) if ev else None
            con.execute("update predictions set outcome=?, scored_at=?, binance_up=?, price_to_beat=? where slug=?",
                        (int(float(prices[0]) == 1.0), iso(now), b_up, ptb, slug))  # fmt: skip
    con.commit()
    rows = con.execute(
        "select p_up_model, p_up_rw, p_up_market, outcome from predictions where outcome is not null"
        " and p_up_market is not null"
    ).fetchall()
    open_n = con.execute("select count(*) from predictions where outcome is null").fetchone()[0]
    print(f"scored predictions: {len(rows)} (still open: {open_n})")
    if not rows:
        return
    a = np.array(rows, dtype=float)
    o = a[:, 3]
    for i, name in enumerate(("timestral", "random_walk", "market")):
        p = np.clip(a[:, i], 1e-4, 1 - 1e-4)
        brier = np.mean((p - o) ** 2)
        ll = -np.mean(o * np.log(p) + (1 - o) * np.log(1 - p))
        acc = np.mean((p > 0.5) == (o == 1))
        print(f"  {name:12s} brier {brier:.4f}  logloss {ll:.4f}  accuracy {acc:.3f}")
    agree = con.execute("select avg(binance_up = outcome), count(*) from (select distinct slug, binance_up,"
                        " outcome from predictions where outcome is not null and binance_up is not null)").fetchone()
    print(f"  Binance direction matched the official result in {agree[0]} of {agree[1]} windows")
    for lo, hi in ((10, 15), (5, 9), (1, 4)):
        b = con.execute("select p_up_model, p_up_market, outcome from predictions where outcome is not null and"
                        " p_up_market is not null and minutes_left between ? and ?", (lo, hi)).fetchall()
        if b:
            x = np.array(b, dtype=float)
            print(f"  {lo}-{hi} min left (n={len(b)}): brier timestral {np.mean((x[:,0]-x[:,2])**2):.4f}"
                  f" market {np.mean((x[:,1]-x[:,2])**2):.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["predict", "score"])
    ap.add_argument("--size", default="28M")
    a = ap.parse_args()
    predict(a.size) if a.cmd == "predict" else score()
    sys.exit(0)
