"""What does a profitable wallet do on BTC 15m Up/Down? Last 14 days of its trades vs Binance and outcomes."""
import json, math, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from live_updown import gamma_market
from replay_updown import binance_range

src = Path(sys.argv[1]); days = float(sys.argv[2]) if len(sys.argv) > 2 else 14
prefix = sys.argv[3] if len(sys.argv) > 3 else "btc-updown-15m"; W = 300 if prefix.endswith("5m") else 900
r = json.loads(src.read_text())
since = time.time() - days * 86400
tr = [x for x in r if x["type"] == "TRADE" and x["slug"].startswith(prefix + "-") and x["timestamp"] >= since]
slugs = sorted({x["slug"] for x in tr})
cache = src.with_suffix(f".{prefix}.outcomes.json")
oc = json.loads(cache.read_text()) if cache.exists() else {}
def res(s):
    m = gamma_market(s)
    p = json.loads(m.get("outcomePrices") or "[]") if m and m.get("closed") else []
    return s, (0 if p[0] in ("1", 1) else 1) if p and sorted(map(float, p)) == [0.0, 1.0] else None  # winning outcome_index
todo = [s for s in slugs if s not in oc]
with ThreadPoolExecutor(8) as ex:
    oc.update(dict(ex.map(res, todo)))
cache.write_text(json.dumps(oc))
k = binance_range("BTCUSDT", int((since - 4000) * 1000), int(time.time() * 1000))
kt = {int(t): i for i, t in enumerate(k[:, 0])}
rows = []
for x in tr:
    w = oc.get(x["slug"]); start = int(x["slug"].rsplit("-", 1)[1]); t = x["timestamp"]
    if w is None or start * 1000 not in kt: continue
    i0 = kt[start * 1000]; il = i0 + (t - start) // 60 - 1  # last completed minute before the trade
    if il < 60 or il >= len(k): continue
    move = math.log(k[il, 2] / k[i0, 1]) if t - start >= 60 else 0.0
    sig = np.diff(np.log(k[il - 60 : il + 1, 2])).std() * math.sqrt(max((start + W - t) / 60, 0.5))
    z = move / sig  # standardized distance from the open, signed toward Up
    side_up = x["outcome_index"] == 0
    rows.append(dict(sec=t - start, price=x["price"], usdc=x["usdc_size"], size=x["size"], buy=x["side"] == "BUY",
                     won=int(x["outcome_index"] == w), with_move=(z > 0) == side_up, z=z * (1 if side_up else -1)))
b = [q for q in rows if q["buy"]]
print(f"{prefix} trades last {days:g} days: {len(tr)}, analysed buys: {len(b)}, markets: {len(slugs)}")
def summ(sel, label):
    if not sel: return
    cost = sum(q["usdc"] for q in sel); pay = sum(q["size"] * q["won"] for q in sel)
    print(f"  {label:34s} n={len(sel):6d} avg price {np.mean([q['price'] for q in sel]):.3f} win {np.mean([q['won'] for q in sel]):.3f}"
          f" cost ${cost:9.0f} pnl ${pay - cost:8.0f} ({(pay - cost) / cost:+.1%})")
summ(b, "all buys")
for f0, f1 in ((0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 13 / 15), (13 / 15, 1.01)):
    lo, hi = f0 * W, f1 * W
    summ([q for q in b if lo <= q["sec"] < hi], f"entered {lo / 60:.1f}-{min(hi, W) / 60:.1f} min in")
for lo, hi in ((0, .5), (.5, .8), (.8, .9), (.9, .95), (.95, 1.01)):
    summ([q for q in b if lo <= q["price"] < hi], f"price {lo:.2f}-{hi:.2f}")
summ([q for q in b if q["with_move"]], "bought the side already ahead")
summ([q for q in b if not q["with_move"]], "bought the side behind")
zs = np.array([q["z"] for q in b]); print("  z of bought side (distance from open in sigmas):", np.percentile(zs, [10, 25, 50, 75, 90]).round(2))
# Fair value check: random-walk P(win) for their side vs the price they paid
fair = np.array([0.5 * (1 + math.erf(q["z"] / math.sqrt(2))) for q in b]); px = np.array([q["price"] for q in b]); won = np.array([q["won"] for q in b])
print(f"  random-walk fair value {fair.mean():.3f} vs price paid {px.mean():.3f} vs realized win {won.mean():.3f}")
for lo, hi in ((-1, 0), (0, .05), (.05, .1), (.1, 1)):
    m_ = (fair - px >= lo) & (fair - px < hi)
    if m_.sum(): print(f"   fair-price edge {lo:+.2f}..{hi:+.2f}: n={m_.sum()} win {won[m_].mean():.3f} paid {px[m_].mean():.3f}")
# Do they react to spot moves? Signed Binance returns (in bp, toward the side bought) around each buy.
def sret(q_idx_off, x, side_up, kk):
    pass
ret = {"prev min": [], "trade min": [], "next min": []}
for x in tr:
    if x["side"] != "BUY" or x["timestamp"] < since: continue
    m0 = (x["timestamp"] // 60) * 60 * 1000
    i = kt.get(m0)
    if i is None or i + 1 >= len(k) or i < 1: continue
    s = 1 if x["outcome_index"] == 0 else -1
    for lab, j in (("prev min", i - 1), ("trade min", i), ("next min", i + 1)):
        ret[lab].append(s * math.log(k[j, 2] / k[j, 1]) * 1e4)
for lab, v in ret.items():
    v = np.array(v); print(f"  {lab}: mean signed move {v.mean():+.2f} bp, share toward their side {np.mean(v > 0):.3f}")
