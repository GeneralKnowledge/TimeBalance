"""Read-only Polymarket snapshot: sports + politics events ending within 30 days.
Usage: python -I scripts/arb_snapshot_polymarket.py data/arb_snapshot/<UTC timestamp>
Writes polymarket_events_raw.jsonl.gz, polymarket_books_raw.json.gz, polymarket_markets.csv (read-only, no auth)."""
import csv, json, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone

OUT = sys.argv[1]
GAMMA = "https://gamma-api.polymarket.com/events"
CLOB = "https://clob.polymarket.com/books"
KEEP = {"sports", "nfl", "nba", "nhl", "epl", "soccer", "premier-league", "tennis", "ufc",
        "mma", "cricket", "politics", "elections", "champions-league", "la-liga", "serie-a",
        "bundesliga", "ligue-1", "atp", "wta", "football"}
UA = {"User-Agent": "timebalance-research/0.1"}


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # noqa
            if i == 3 or getattr(e, "code", 0) in (406, 422):
                raise
            time.sleep(2 ** i)


now = datetime.now(timezone.utc)
end_max = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
import gzip
raw = gzip.open(f"{OUT}/polymarket_events_raw.jsonl.gz", "wt")
events, seen, off = [], set(), 0
for tag in ("sports", "politics"):
    off = 0
    while True:
        q = urllib.parse.urlencode({"closed": "false", "active": "true", "limit": 50, "offset": off, "tag_slug": tag,
                                    "end_date_max": end_max, "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
        try:
            page = get(f"{GAMMA}?{q}")
        except urllib.error.HTTPError as ex:  # API caps offset paging (422)
            print(tag, "stopped at offset", off, ex, file=sys.stderr)
            break
        if not page:
            break
        for e in page:
            tags = {t.get("slug") for t in e.get("tags") or []}
            if e["id"] not in seen and tags & KEEP:
                seen.add(e["id"])
                raw.write(json.dumps(e) + "\n")
                e = {k: e.get(k) for k in ("id", "title", "slug", "startTime", "endDate", "markets")}
                MK = ("id", "question", "slug", "outcomes", "outcomePrices", "clobTokenIds", "bestBid", "bestAsk",
                      "endDate", "gameStartTime", "sportsMarketType", "liquidityNum", "liquidity", "active", "closed")
                e["markets"] = [{k: m.get(k) for k in MK} for m in e.get("markets") or []]
                e["_tags"] = sorted(t for t in tags if t)
                events.append(e)
        off += len(page)
        print(tag, off, file=sys.stderr)
        if len(page) < 50 or off >= 3000:
            break
raw.close()
print("pages scanned:", off, "kept events:", len(events), file=sys.stderr)

rows, tokens = [], []
for e in events:
    for m in e.get("markets") or []:
        if m.get("closed") or not m.get("active", True):
            continue
        outs = json.loads(m.get("outcomes") or "[]")
        prices = json.loads(m.get("outcomePrices") or "[]")
        toks = json.loads(m.get("clobTokenIds") or "[]")
        tokens += toks
        rows.append(dict(event_id=e["id"], event_title=e.get("title"), event_slug=e.get("slug"),
                         tags="|".join(e["_tags"]), market_id=m.get("id"), question=m.get("question"),
                         slug=m.get("slug"), outcomes="|".join(outs), outcome_prices="|".join(prices),
                         best_bid=m.get("bestBid"), best_ask=m.get("bestAsk"), end_date=m.get("endDate"),
                         game_start=m.get("gameStartTime") or e.get("startTime"),
                         sports_market_type=m.get("sportsMarketType"),
                         liquidity=m.get("liquidityNum") or m.get("liquidity"),
                         yes_token=toks[0] if toks else None, no_token=toks[1] if len(toks) > 1 else None))

# top-of-book sizes from the public CLOB (batch endpoint)
books = {}
for i in range(0, len(tokens), 200):
    chunk = [{"token_id": t} for t in tokens[i:i + 200]]
    try:
        for b in get(CLOB, json.dumps(chunk).encode()) or []:
            books[b["asset_id"]] = b
    except Exception as ex:  # noqa
        print("book batch failed:", ex, file=sys.stderr)


def top(b):
    if not b:
        return (None,) * 4
    bids = sorted(b.get("bids") or [], key=lambda x: -float(x["price"]))
    asks = sorted(b.get("asks") or [], key=lambda x: float(x["price"]))
    f = lambda l, k: float(l[0][k]) if l else None
    return f(bids, "price"), f(bids, "size"), f(asks, "price"), f(asks, "size")


for r in rows:
    r["yes_bid"], r["yes_bid_size"], r["yes_ask"], r["yes_ask_size"] = top(books.get(r["yes_token"]))
    r["no_bid"], r["no_bid_size"], r["no_ask"], r["no_ask_size"] = top(books.get(r["no_token"]))

json.dump(books, gzip.open(f"{OUT}/polymarket_books_raw.json.gz", "wt"))
with open(f"{OUT}/polymarket_markets.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["empty"])
    w.writeheader(); w.writerows(rows)
print(json.dumps({"events": len(events), "markets": len(rows), "books": len(books)}))
