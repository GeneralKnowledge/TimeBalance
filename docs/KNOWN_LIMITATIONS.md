# Known limitations

_As of M1.1 (2026-11-03)._

## Hardware and dependencies

- **GTX 1060 support depends on the torch build.** We use `torch 2.14.1+cu126`, whose arch list
  includes `sm_60` (binary-compatible with the 1060's `sm_61`). Default PyPI wheels (CUDA 12.8+)
  have no Pascal kernels. Upgrading torch or moving off the cu126 index may silently lose GPU
  support; `mpe.models.timestral.cuda_usable()` then reports why and `device="auto"` falls back
  to CPU. Always check `torch.cuda.get_arch_list()` after an upgrade.
- The CUDA runtime keeps ~780 MB of host RAM for the life of any process that has used the GPU.
- Unload relies on two low-level calls: `torch._C._cuda_clearCublasWorkspaces()` (private PyTorch
  API, guarded) and glibc `malloc_trim` (Linux only). Without them, an 8 MiB cuBLAS workspace stays
  allocated and freed host memory may not return to the OS (we measured ~440 MB retained after 209M).
- fp16 is not used: it is 2× slower than fp32 on Pascal, and upstream validated only fp32.

## Timestral

- Quantile levels are fixed to the 21 trained levels in [0.01, 0.99]. Other levels inside that
  range are linear interpolations between trained levels; levels outside it are refused.
- Upstream non-negative clipping is turned **off** in our adapter (upstream default is on). If a
  future experiment forecasts raw non-negative levels (volume, prices), decide explicitly.
- Horizons are capped at 1,024 steps (one decode block). Upstream can go further by feeding back
  medians, but those forecasts are recursive and not comparable.
- No frequency argument exists; the model only sees the value sequence.
- Per-step quantiles do not add up across steps. The demo's "implied price" is the median-path
  price (`exp(cumsum(median returns))`), not the median of the h-day price distribution. Direct
  h-step targets (h-day cumulative returns) are needed for proper multi-day price intervals (M2).
- The covariate path (multivariate targets, past and known-future covariates) is exercised with a
  tiny random-weight network in unit tests and runs through the adapter, but it has not yet been
  evaluated with real weights on real data. That belongs to the M2 experiments.
- One series per call; upstream batching is not used yet.

## Baselines

- Baselines treat series independently and accept no covariates (they raise rather than ignore).
- Their median is the 0.5 quantile of point forecast + in-sample errors, so it includes the
  method's median bias; `persistence` therefore does not return exactly the last value.
- On return targets `persistence` and `momentum` act on returns, not prices. `zero` is the price
  random walk for log-return targets.

## Fixtures and calendars

- `make_input` steps future timestamps by a fixed interval (1 day for SPY); it is not
  trading-calendar aware. Calendar-aware targets come with the data layer in M1.
- SPY fixture timestamps are Yahoo session-open times in UTC (14:30Z), not session close; the
  M1 provider must set `timestamp` and `available_at` properly.
- The Polymarket fixture is one high-profile resolved market (2024 US presidential election,
  YES = Trump), hourly CLOB `prices-history` snapped to the hour, 2024-09-05 to 2024-11-06. The
  demo cuts its context at 2024-11-05 00:00Z, before the result was known. Not representative of
  typical markets.
- `prices-history` returned nothing for this resolved market with `interval=max`; it needed
  explicit `startTs`/`endTs` windows of at most ~14 days. Note this for the M1 provider.

## Data ingestion (M1, 2026-11-03)

- **Yahoo is unofficial.** `yfinance` scrapes Yahoo's chart API; it can throttle, break or change
  without notice, and its terms allow personal research use only. There is no second stock source
  yet: Stooq's CSV endpoint is behind a JavaScript challenge and Alpha Vantage's free tier (25
  requests/day, key required) is too small for backfills.
- **Yahoo back-adjusts.** `close` is split-adjusted after the fact, so a split rewrites history.
  A backfilled `close` is therefore already split-adjusted for splits that came after the
  simulated cutoff. Returns are unaffected, and the split day shows no artificial jump. Price
  levels before a split are not the prices quoted at the time.
  We keep each change as a new `version` row, but anything that read the old version saw
  different numbers (which is the point of versioning, and also why M2 must read through
  `get_history`). Prices are rounded to the 7 significant digits Yahoo's float32 values carry.
- **Daily bars are close-only knowledge.** `available_at` = session close + 30 min. The open of a
  day is in fact known earlier; M2/M3 must not use a same-day open to decide at the open.
- **FX bars** are treated as ending at 00:00 London, and Yahoo FX data has many bars whose open or
  close lies outside the high-low range (91 since 2010 for GBP/USD; logged as `ohlc_inconsistent`).
- **Polymarket hourly history is a sample, not a bar.** CLOB `prices-history` gives one price per
  roughly hour; we file it under its hour with the true sample time in `source_ts`. There is no
  open/high/low, and quiet markets have gaps (logged as `history_gaps`, never filled).
- **Polymarket trade volume is partial for busy markets.** Each run reads at most 5 pages (5,000
  trades) of the newest trades per market and keeps only complete hours. Busy markets therefore
  get recent volume only; there is no volume backfill for older history. Trade volume is not
  collected for resolved markets.
- **Book snapshots only from now on.** Order books cannot be fetched historically, so
  `order_book_snapshots` start with the first run. Snapshot `close` is the bid/ask midpoint and
  flagged `close_is_midpoint`; it must never be used as an execution price.
- **Selection bias.** The panel is chosen by lifetime volume, so it leans to geopolitics, US
  politics and crypto prices; multi-outcome (negRisk) events are excluded entirely. All scanned
  markets are stored with `selection_reason` so this can be quantified.
- **Resolved markets** come only from the last 365 days of closes, and `resolutions.resolved_at`
  is the Data API's last resolution update, which can be later than the moment the outcome was
  effectively known.
- **The scheduler is systemd timers for now** (`deploy/`), not APScheduler. It runs one job per
  slot (enforced by `job_runs`), but there is no in-process retry within a slot; the next slot
  picks up where the last one stopped.

## Historical replay and price field (M1.1, 2026-11-03)

How the two replay modes work is described in `docs/DATA_SOURCES.md`, under "Reading history".

- **Reconstructed history is not contemporaneous knowledge.** Almost all data before 2026-11-03
  was backfilled, so strict replay of any earlier date is empty. Reconstructed replay uses each
  row's availability rule instead. It is an assumption ("Yahoo's close was known 30 minutes after
  the close"), not an observation of when we actually knew the value. Results based on it must be
  labelled as reconstructed (`attrs["replay"]`).
- **Revisions that were never captured are lost.** Reconstructed replay uses the earliest version
  we hold. If the provider revised a value before our first download, we only have the revised
  value, and there is no way to recover what the value was at the time. Versioning only records
  revisions made after the first capture.
- **Availability rules are per source.** They cover the four sources that M1 ingests. A new source
  needs a rule before reconstructed replay will read it. Order-book snapshots can never be
  reconstructed.
- **Close, not adjusted close.** Initial stock forecasting uses `close`, so return targets are
  price returns. They exclude dividends (roughly 1–1.5% a year on SPY), which is a small, known bias
  against total-return comparisons. `adj_close` is kept but is not used as an input.
- **Corporate actions are not modelled.** Splits are already applied retrospectively in `close`
  (see above). Dividends are kept as `dividend:x` flags on the ex-date bar but are not yet used.
  Total-return forecasting will need dividends applied from their ex-date, with an explicit rule
  for when each dividend became known. That is not built yet.
- **M0 SPY numbers predate this change.** The M0 demo and sanity figures in `docs/STATUS.md` were
  computed from `adj_close`. The scripts now use `close`, so their output differs slightly.
