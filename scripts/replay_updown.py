"""Replay resolved 15-minute crypto Up/Down markets: Timestral vs market price vs random walk.

At fixed points in each window (minutes left = 14, 10, 5, 2) we use only data available then:
Binance 1-minute closes up to that minute and the last Polymarket trade price at or before it.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from live_updown import ASSETS, BINANCE, CLOB, CONTEXT_MIN, LEVELS, WINDOW, cdf_at, gamma_market, http
from mpe.models.base import ForecastInput
from mpe.models.timestral import TimestralModel

CACHE = Path(__file__).resolve().parents[1] / "data" / "replay_cache.json"
MINUTES_LEFT = (14, 10, 5, 2)


def binance_range(symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
    rows, t = [], start_ms
    while t < end_ms:
        raw = http.get(BINANCE, params={"symbol": symbol, "interval": "1m", "startTime": t, "limit": 1000}).json()
        if not raw:
            break
        rows += [(int(k[0]), float(k[1]), float(k[4])) for k in raw]
        t = int(raw[-1][0]) + 60_000
    return np.array([r for r in rows if r[0] < end_ms])


def fetch_window(asset: str, start: int) -> dict | None:
    slug = f"{asset}-updown-15m-{start}"
    m = gamma_market(slug)
    if not m or not m.get("closed"):
        return None
    prices = [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]
    if sorted(prices) != [0.0, 1.0]:
        return None
    tok = json.loads(m["clobTokenIds"])[0]
    hist = http.get(f"{CLOB}/prices-history",
                    params={"market": tok, "startTs": start - 600, "endTs": start + WINDOW, "fidelity": 1}).json()  # fmt: skip
    return {"slug": slug, "asset": asset, "start": start, "outcome": int(prices[0] == 1.0),
            "hist": [(int(h["t"]), float(h["p"])) for h in hist.get("history", [])]}  # fmt: skip


def collect(hours: float) -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    last = int(time.time() // WINDOW * WINDOW) - 2 * WINDOW  # leave time for resolution
    starts = list(range(last - int(hours * 3600) + WINDOW, last + 1, WINDOW))
    jobs = [(a, s) for a in ASSETS for s in starts]
    with ThreadPoolExecutor(8) as ex:
        windows = [w for w in ex.map(lambda j: fetch_window(*j), jobs) if w]
    lo, hi = (starts[0] - CONTEXT_MIN * 60) * 1000, (last + WINDOW) * 1000
    klines = {a: binance_range(sym, lo, hi).tolist() for a, sym in ASSETS.items()}
    data = {"windows": windows, "klines": klines}
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(data))
    return data


def main(hours: float, size: str) -> None:
    data = collect(hours)
    k_all = {a: np.array(v) for a, v in data["klines"].items()}
    model = TimestralModel(size)
    model.load("cpu")
    rows, agree = [], []
    for w in data["windows"]:
        k = k_all[w["asset"]]
        idx = {int(t): i for i, t in enumerate(k[:, 0])}
        i0 = idx.get(w["start"] * 1000)
        if i0 is None:
            continue
        strike = k[i0, 1]
        i_end = i0 + 14
        if i_end < len(k):
            agree.append(int(k[i_end, 2] > strike) == w["outcome"])
        hist = w["hist"]
        for h in MINUTES_LEFT:
            t = w["start"] + (15 - h) * 60  # decision time = close of the last completed minute
            i_last = i0 + (15 - h) - 1
            if i_last < CONTEXT_MIN or i_last >= len(k):
                continue
            mk = [p for ts, p in hist if ts <= t]
            if not mk:
                continue
            ctx = k[i_last - CONTEXT_MIN + 1 : i_last + 1]
            y = np.log(ctx[:, 2] / strike)
            ts = (ctx[:, 0] / 1000 + 60).astype("datetime64[s]")
            fut = np.array([ts[-1] + np.timedelta64(60 * (j + 1), "s") for j in range(h)])
            out = model.forecast(ForecastInput(
                values=y, timestamps=ts, series_names=[w["asset"]], horizon=h,
                input_cutoff=datetime.fromtimestamp(t, UTC), future_timestamps=fut, quantile_levels=LEVELS,
            ))  # fmt: skip
            p_ts = 1 - cdf_at(0.0, np.asarray(out.quantiles)[0, -1], LEVELS)
            r = np.diff(np.log(ctx[-61:, 2]))
            sig = r.std(ddof=1) * math.sqrt(h)
            p_rw = 1 - 0.5 * (1 + math.erf(-y[-1] / (sig * math.sqrt(2)))) if sig > 0 else float(y[-1] > 0)
            rows.append((h, w["asset"], p_ts, p_rw, mk[-1], w["outcome"]))

    print(f"windows: {len(data['windows'])}, predictions: {len(rows)}, model timestral-{size}")
    print(f"Binance direction matched the official (Chainlink) result in {np.mean(agree):.3f} of {len(agree)} windows")
    names = ("timestral", "random_walk", "market")
    for h in MINUTES_LEFT:
        a = np.array([r[2:] for r in rows if r[0] == h], dtype=float)
        if not len(a):
            continue
        o = a[:, 3]
        line = [f"{h:2d} min left (n={len(a)}):"]
        for i, n in enumerate(names):
            p = np.clip(a[:, i], 1e-4, 1 - 1e-4)
            line.append(f"{n} brier {np.mean((p - o) ** 2):.4f} acc {np.mean((p > 0.5) == (o == 1)):.3f}")
        print("  " + " | ".join(line))
    # Does Timestral add anything once the market price is known? Brier of a 50/50 blend vs market alone.
    a = np.array([r[2:] for r in rows], dtype=float)
    o = a[:, 3]
    blend = 0.5 * a[:, 0] + 0.5 * a[:, 2]
    print(f"all: market brier {np.mean((a[:, 2] - o) ** 2):.4f}, 50/50 timestral+market {np.mean((blend - o) ** 2):.4f}")
    out = CACHE.with_name("replay_rows.json")
    out.write_text(json.dumps(rows))
    print(f"rows saved to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=48)
    ap.add_argument("--size", default="28M")
    a = ap.parse_args()
    main(a.hours, a.size)
