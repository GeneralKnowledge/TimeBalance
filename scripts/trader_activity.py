"""Download a Polymarket wallet's full public activity (Data API v2, cursor pagination) to JSON."""
import json, sys, time
from pathlib import Path
from live_updown import http

wallet, out = sys.argv[1], Path(sys.argv[2])
since = time.time() - float(sys.argv[3]) * 86400 if len(sys.argv) > 3 else 0  # optional: only the last N days
rows, cursor = [], None
while True:
    params = {"user": wallet, "limit": 500}
    if cursor:
        params["cursor"] = cursor
    page = http.get("https://data-api.polymarket.com/v2/activity", params=params).json()
    rows += page.get("data", [])
    cursor = (page.get("pagination") or {}).get("next_cursor")
    if not cursor or not page.get("data") or page["data"][-1]["timestamp"] < since:
        break
out.write_text(json.dumps(rows))
print(len(rows), "rows")
