"""One-off: turn raw downloads into the small committed fixtures in tests/fixtures/.

Inputs (fetched once by hand, not committed):
  spy.json         Yahoo chart API, SPY, range=10y, interval=1d
  pm_chunk_*.json  Polymarket CLOB /prices-history, fidelity=60, 14-day windows, for the YES token
                   of "Will Donald Trump win the 2024 US Presidential Election?"
Usage: python scripts/build_fixtures.py <download_dir>
"""

import csv
import glob
import json
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def spy(src: Path) -> None:
    r = json.loads((src / "spy.json").read_text())["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    adj = r["indicators"]["adjclose"][0]["adjclose"]
    rows = [
        (iso(t), o, h, lo, c, a, v)
        for t, o, h, lo, c, a, v in zip(
            r["timestamp"], q["open"], q["high"], q["low"], q["close"], adj, q["volume"]
        )
        if c is not None
    ][-1500:]
    with open(OUT / "spy_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "adj_close", "volume"])
        for row in rows:
            w.writerow([row[0], *(f"{x:.4f}" for x in row[1:6]), int(row[6])])
    print("spy_daily.csv", len(rows), rows[0][0], rows[-1][0])


def polymarket(src: Path) -> None:
    pts = {}
    for p in sorted(glob.glob(str(src / "pm_chunk_*.json"))):
        for h in json.loads(Path(p).read_text())["history"]:
            pts[int(h["t"]) // 3600 * 3600] = float(h["p"])  # snap to the hour
    rows = sorted(pts.items())[-1500:]
    with open(OUT / "pm_yes_hourly.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "yes_price"])
        for t, p in rows:
            w.writerow([iso(t), f"{p:.4f}"])
    print("pm_yes_hourly.csv", len(rows), iso(rows[0][0]), iso(rows[-1][0]))


def sine() -> None:
    rng = random.Random(42)
    with open(OUT / "sine_noise.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "value", "noiseless"])
        for t in range(1200):
            clean = 10 * math.sin(2 * math.pi * t / 24) + 0.01 * t
            w.writerow([t, f"{clean + rng.gauss(0, 0.5):.6f}", f"{clean:.6f}"])
    print("sine_noise.csv 1200")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    d = Path(sys.argv[1])
    spy(d)
    polymarket(d)
    sine()
