"""Paper-only live test: Timestral 24-hour forecasts of open Polymarket markets' own prices.

`predict`: take the most-traded open binary markets that close more than 2 days out, fetch ~3 weeks of
hourly YES prices, forecast the logit price 24 h ahead with Timestral, and log the median and quantiles
next to the "price stays the same" baseline. `score`: once 24 h have passed, fetch the realised price and
compare absolute errors and direction calls.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta

import numpy as np

from live_updown import CLOB, GAMMA, LEVELS, ROOT, http, iso
from mpe.features.transforms import inv_logit, logit
from mpe.models.base import ForecastInput
from mpe.models.timestral import TimestralModel

DB = ROOT / "data" / "live_markets.sqlite3"
H = 24
SCHEMA = """
create table if not exists forecasts (
  id integer primary key, created_at text, condition_id text, question text, token_id text,
  last_ts integer, last_price real, target_ts integer, model text, median real, quantiles text,
  realized real, scored_at text, unique(condition_id, last_ts))
"""


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute(SCHEMA)
    return c


def hourly(token: str, start: int, end: int) -> list[tuple[int, float]]:
    pts = {}
    t = start
    while t < end:
        t2 = min(t + 14 * 86400, end)
        h = http.get(f"{CLOB}/prices-history", params={"market": token, "startTs": t, "endTs": t2, "fidelity": 60}).json()
        for p in h.get("history", []):
            pts[int(p["t"]) // 3600 * 3600] = float(p["p"])  # last sample in each hour wins
        t = t2
    return sorted(pts.items())


def candidates(n: int) -> list[dict]:
    soon = datetime.now(UTC) + timedelta(days=2)
    out, markets, cursor = [], [], None
    for _ in range(5):  # up to 500 markets by 24h volume
        params = {"limit": 100, "closed": "false", "order": "volume24hr", "ascending": "false"}
        if cursor:
            params["after_cursor"] = cursor
        page = http.get(f"{GAMMA}/markets/keyset", params=params).json()
        markets += page.get("markets", [])
        cursor = page.get("next_cursor")
        if not cursor:
            break
    for m in markets:
        try:
            end = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
            p = float(json.loads(m["outcomePrices"])[0])
        except (KeyError, TypeError, ValueError):
            continue
        if end > soon and 0.03 < p < 0.97 and len(json.loads(m.get("clobTokenIds") or "[]")) == 2:
            out.append(m)
        if len(out) >= n:
            break
    return out


def predict(n: int, size: str) -> None:
    model = TimestralModel(size)
    model.load("cpu")
    con = db()
    now = int(time.time())
    cur_hour = now // 3600 * 3600
    for m in candidates(n):
        tok = json.loads(m["clobTokenIds"])[0]
        pts = [(t, p) for t, p in hourly(tok, now - 21 * 86400, now) if t < cur_hour]  # completed hours only
        if len(pts) < 7 * 24:
            continue
        ts = np.array([t for t, _ in pts])
        grid = np.arange(ts[0], ts[-1] + 1, 3600)  # forward-fill gaps onto a regular hourly grid
        pr = np.array([dict(pts).get(t, np.nan) for t in grid])
        for i in range(1, len(pr)):
            if np.isnan(pr[i]):
                pr[i] = pr[i - 1]
        last_ts = int(grid[-1])
        tstamps = (grid + 3600).astype("datetime64[s]")  # each hour's value is known at its end
        fut = np.array([tstamps[-1] + np.timedelta64(3600 * (j + 1), "s") for j in range(H)])
        out = model.forecast(ForecastInput(
            values=logit(pr), timestamps=tstamps, series_names=[m["conditionId"]], horizon=H,
            input_cutoff=datetime.fromtimestamp(last_ts + 3600, UTC), future_timestamps=fut, quantile_levels=LEVELS,
        ))  # fmt: skip
        q = inv_logit(np.asarray(out.quantiles)[0, -1])
        med = float(inv_logit(np.asarray(out.values)[0, -1]))
        con.execute(
            "insert or ignore into forecasts (created_at, condition_id, question, token_id, last_ts, last_price,"
            " target_ts, model, median, quantiles) values (?,?,?,?,?,?,?,?,?,?)",
            (iso(now), m["conditionId"], m["question"], tok, last_ts, float(pr[-1]), last_ts + H * 3600,
             out.model.name, med, json.dumps([round(float(v), 5) for v in q])),
        )  # fmt: skip
        print(f"{pr[-1]:.3f} -> {med:.3f} [{q[2]:.3f}, {q[-3]:.3f}]  {m['question'][:80]}")
    con.commit()


def score() -> None:
    con = db()
    now = int(time.time())
    for fid, tok, target in con.execute(
        "select id, token_id, target_ts from forecasts where realized is null and target_ts + 3600 <= ?", (now,)
    ).fetchall():
        pts = hourly(tok, target - 3 * 3600, target + 3600)
        at = [p for t, p in pts if t <= target]
        if at:
            con.execute("update forecasts set realized=?, scored_at=? where id=?", (at[-1], iso(now), fid))
    con.commit()
    rows = con.execute("select last_price, median, realized, quantiles from forecasts where realized is not null").fetchall()
    open_n = con.execute("select count(*) from forecasts where realized is null").fetchone()[0]
    print(f"scored forecasts: {len(rows)} (still open: {open_n})")
    if not rows:
        return
    a = np.array([r[:3] for r in rows])
    moved = a[:, 2] != a[:, 0]
    print(f"  MAE timestral {np.mean(np.abs(a[:, 1] - a[:, 2])):.4f}  MAE no-change {np.mean(np.abs(a[:, 0] - a[:, 2])):.4f}")
    d = moved & (a[:, 1] != a[:, 0])
    if d.any():
        print(f"  direction right on {np.mean(np.sign(a[d, 1] - a[d, 0]) == np.sign(a[d, 2] - a[d, 0])):.3f} of {d.sum()} that moved")
    inside = [json.loads(r[3])[2] <= r[2] <= json.loads(r[3])[-3] for r in rows]
    print(f"  realised price inside the 10-90% range: {np.mean(inside):.3f} (target 0.8)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["predict", "score"])
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--size", default="28M")
    a = ap.parse_args()
    predict(a.n, a.size) if a.cmd == "predict" else score()
