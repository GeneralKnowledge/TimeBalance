# Data sources

_Checked live from the laptop on 2026-11-03 (M1). All sources are free and read-only. No source
needs credentials, and none is called with any._

## Summary

| Source | Used for | Access | Limits we respect | Status |
|---|---|---|---|---|
| Polymarket Gamma API | Market discovery, metadata, token ids, resolution status | Public, no key | 300 req/10 s on `/markets` | In use |
| Polymarket CLOB API | Hourly price history, live order books | Public read endpoints, no key | 1,000 req/10 s on `/prices-history`, 1,500 on `/book` | In use |
| Polymarket Data API v2 | Trade feed (aggregated to hourly volume), resolution state | Public, no key | 300 req/10 s on `/v2/trades`, 800 general | In use |
| Yahoo Finance via `yfinance` | Daily OHLCV, adjusted close, dividends, splits, GBP/USD | Unofficial, no key | Self-throttled; retries with backoff | In use |
| Stooq | Daily CSVs | Blocked | n/a | Not usable: CSV URLs return a JavaScript challenge page |
| Alpha Vantage | Daily OHLCV | Needs a free key | 25 requests/day on the free tier | Not implemented (see below) |

Our own extra cap: `polymarket.daily_request_budget` (default 20,000/day), counted per UTC day in
`system_state` (`request_budget:polymarket:<date>`) so it survives restarts and rolled-back runs.
A full backfill of 47 markets took about 1,900 requests; an incremental update about 350.

## Polymarket

Docs: https://docs.polymarket.com/ (index at `/llms.txt`; OpenAPI specs at `/api-spec/clob-openapi.yaml`,
`/api-spec/gamma-openapi.yaml` and `https://data-api.polymarket.com/v2/openapi.json`). Rate limits
are IP-based Cloudflare throttles (requests are delayed or queued rather than rejected; we still
treat 429 and 5xx as retryable with exponential backoff and honour `Retry-After`).

### Gamma API: `https://gamma-api.polymarket.com`

- `GET /markets/keyset?limit=100&closed=false|true&order=volumeNum&ascending=false[&end_date_min=…]`
  Cursor pagination: pass `next_cursor` back as `after_cursor`. `offset` is rejected (422).
  `order` takes camelCase field names (`volumeNum`); snake_case gives 422.
- Lookup by id: `condition_ids=<id>&closed=any` (repeat the parameter; `closed=any` is only
  allowed with an identifier filter).
- Fields we use: `conditionId` (our `provider_market_id`), `question`, `slug`, `description` (the
  resolution rules), `outcomes` and `clobTokenIds` (JSON strings, same order, so YES/NO token ids
  come from the position of "Yes"/"No"), `negRisk`, `startDate`, `endDate`, `closedTime`,
  `closed`, `umaResolutionStatus`, `outcomePrices`, `liquidityNum`, `volumeNum`, `feesEnabled`,
  `feeSchedule`, `events[0].id/slug`. The full payload is kept in `markets.raw_json`.
- `negRisk: true` means the market is one leg of a multi-outcome event (each leg is itself a
  Yes/No market). We exclude these initially, as the brief asks for binary markets only.
- Resolution mapping: open while `closed` is false; `resolved` when `umaResolutionStatus` is
  `resolved` and `outcomePrices` is `["1","0"]` (YES) or `["0","1"]` (NO), `["0.5","0.5"]` is SPLIT;
  other final prices are `ambiguous`; `disputed` is kept as such; closed without resolution is
  `closed`. Ambiguous and disputed markets are excluded from the panel.

### CLOB API: `https://clob.polymarket.com`

- `GET /prices-history?market=<token_id>&startTs=<s>&endTs=<s>&fidelity=60` gives one sample per
  ~hour (`{"history":[{"t":…, "p":…}]}`). **Windows longer than ~14 days are rejected with HTTP
  400** ("interval is too long"), so history is fetched in 14-day windows. `interval=max` returns
  only ~30 days for active markets and nothing for many resolved ones, so we never rely on it.
  Samples are not on the hour; we file each under its hour (`timestamp` = hour start) and keep
  the real sample time in `source_ts`. If an hour has several samples the latest wins. The
  current, still-forming hour is never stored.
- `GET /book?token_id=<id>` returns the live book with a millisecond `timestamp`. Levels arrive
  worst-first (bids ascending, asks descending); we store them best-first in
  `order_book_snapshots` as decimal strings.
- `/price`, `/midpoint`, `/spread` exist; not used, as the book carries the same information.

### Data API v2: `https://data-api.polymarket.com`

**Data API v1 was retired on 2026-11-02** (v1 routes now return HTTP 410). v2 differences that
matter: responses are wrapped in `{"data": …, "pagination": {…}}`, fields are snake_case, markets
are selected with `condition=` (not `market=`, which gives 400), up to 20 ids per call, and
pagination is cursor-only (`pagination.next_cursor`; `offset` gives 400).

- `GET /v2/trades?condition=<id>&limit=1000` then `&cursor=…`: the trade feed, newest first,
  taker side only by default (so each fill is counted once). We aggregate it into hourly volume
  (shares) and trade counts per token, emitting only hours known to be complete: never the
  current hour, and not the oldest hour reached if we stopped paginating early
  (`polymarket.trades.max_pages_per_market`, default 5 pages). Rows include wallet addresses and
  user names; **we do not store any per-trade or per-user data.**
- `GET /v2/resolutions?condition=<ids>`: resolution state (`status`, `was_disputed`, `price`,
  `last_update_timestamp`). We use `last_update_timestamp` as `resolutions.resolved_at`; the
  outcome itself comes from Gamma `outcomePrices`.
- `GET /v2/prices-history` (new in v2) can serve a market's whole life at 3-hour or 12-hour
  buckets (`interval=max&bucket_seconds=10800`), and resolved series end with a settlement point.
  Finer data is windowed (1-minute for ≥ 7 days, 5-minute ≥ 60, 30-minute ≥ 90). Not used yet:
  the CLOB endpoint gives hourly data for whole market lives, which matches our 1/6/24-hour
  horizons. It is the fallback if the CLOB history endpoint is ever retired.
- `GET /v2/oi?condition=…` (open interest) works; not stored yet.

### Fees and trading constraints (for M3)

Taker fee = `shares × feeRate × p × (1 − p)` (makers pay nothing). Rates by category: crypto
0.07; sports, economics, culture, weather, other 0.05; finance, politics, mentions, tech 0.04;
geopolitics 0. We store `feeSchedule.rate × 10,000` in `markets.fee_bps` (so `400` means rate
0.04, not a flat 4%); `0` when `feesEnabled` is false. Gamma also gives `orderPriceMinTickSize`
and `orderMinSize` (kept in `raw_json`).

### Market selection (`polymarket.selection` in `config/settings.yaml`)

Each run scans up to 600 open markets and 600 markets closed in the last 365 days, highest volume
first. A market is eligible when it is Yes/No binary, not a negRisk leg, has resolution rules, has
at least 14 days of history, is not ambiguous or disputed, and either (open) has liquidity ≥
$20,000 and volume ≥ $100,000, or (resolved) has lifetime volume ≥ $250,000. The top 35 open and
top 12 resolved by volume are selected. **Every scanned market is stored**, selected or not, with
`selection_reason`, so the selection itself can be audited for bias. Once selected, a market stays
in the panel (it is not swapped out when something more popular appears).

Known selection bias: ranking by volume favours geopolitics, US politics and crypto-price
markets. The first live panel (2026-11-03) was dominated by Iran / Taiwan / Russia questions and
Bitcoin price thresholds. Category quotas are a possible later change.

## Yahoo Finance (`yfinance` 1.7)

- Unofficial scraping of Yahoo's chart API. Yahoo's terms allow personal, non-commercial use
  only; this project qualifies. No SLA: it can break, throttle or change without notice. We call
  `Ticker.history(start, end, interval="1d", auto_adjust=False, actions=True)` once per symbol per
  run and retry failures with exponential backoff.
- `Close` is split-adjusted but not dividend-adjusted; `Adj Close` is adjusted for both. We store
  both, plus dividends and splits as flags on the bar (`quality_flags: ["dividend:0.48"]`).
  Because Yahoo back-adjusts history after every split, a past `close` can change; such changes
  arrive as new `version` rows.
- Yahoo recomputes `Adj Close` on every request and its last digit wobbles (84.5923, then
  84.59229). Changes under 1e-5 relative in `adj_close` are therefore not treated as corrections
  (a real dividend re-adjustment is far larger). Every other field must match exactly.
- Yahoo serves float32 prices (768.79 arrives as 768.7899780273438). We keep 7 significant digits,
  which is all float32 carries.
- Timestamps: Yahoo labels daily bars with the local session date. We set `timestamp` to the
  session's close from the XNYS calendar (`exchange_calendars`, which knows holidays, early closes
  and DST) and `available_at = close + 30 min`. FX bars (`GBPUSD=X`) are labelled with the London
  date; we treat a bar as ending at the next 00:00 Europe/London. Bars still forming at retrieval
  time are not stored.
- History: SPY, QQQ, IWM, GLD, TLT, MSFT, AAPL, AMZN, NVDA and ^VIX from 2010-01-04; GBP/USD from
  2010-01-01. Updates re-read the last 10 days so Yahoo revisions are caught.

## Stooq

Free daily CSVs at `https://stooq.com/q/d/l/?s=spy.us&i=d`, but as of 2026-11-03 every request
(including with a browser User-Agent) gets a JavaScript browser-verification page instead of CSV.
Not usable from a headless job, so no adapter was written.

## Alpha Vantage

Free tier: 25 requests/day and a free API key (the `demo` key no longer returns data). Real-time
and 15-minute-delayed US data are paid. Enough for a daily cross-check of one or two symbols, not
for backfills. Not implemented in M1 because yfinance covers the watchlist; it would be the first
fallback if Yahoo stops working. Adding it means one more class implementing
`MarketDataProvider` (`list_instruments`, `fetch_history`, `fetch_latest`).

## Provenance and `available_at`

Every observation row records `source`, `source_ts` (time reported by the source, where there is
one), `retrieved_at` (our fetch time), `available_at` (earliest time we could have known the
value) and `version`.

| Data | `timestamp` | `available_at` |
|---|---|---|
| Daily stock / ETF / index bar | Session close (UTC) | Close + 30 min |
| Daily FX bar | Next 00:00 London (UTC) | That + 30 min |
| Polymarket hourly history | Hour start | Sample time + 60 s (never later than `retrieved_at`) |
| Polymarket hourly trade volume | Hour start | Hour end + 60 s (never later than `retrieved_at`) |
| Polymarket book snapshot | `retrieved_at` | `retrieved_at` |

The point-in-time accessor `mpe.storage.repositories.get_history(asset_id, as_of, interval)`
returns only rows with `available_at <= as_of` and `retrieved_at <= as_of`, and for each
timestamp the latest such version.
