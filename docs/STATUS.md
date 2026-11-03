# Status

_Last updated 2026-11-03._

## Milestones

| Milestone | State |
|---|---|
| M0 Foundation and Timestral integration | Done (PR #2, merged) |
| M1 Data ingestion and persistence | Done (PR #3, merged) |
| M1.1 Historical data integrity and ingestion reliability | Done (PR #4, merged) |
| M2 Forecasting research laboratory | Current: branch `milestone/m2-forecasting-lab`, PR open for review |
| M3–M5 | Not started |

## Environment (laptop `create`)

Ubuntu, kernel 6.8; Intel i7-8750H (6 cores / 12 threads); 7.6 GB RAM + 4 GB swap; NVIDIA GTX 1060
Max-Q 6 GB (compute capability 6.1), driver 550.163.01 (CUDA 12.4); Python 3.12.3; uv 0.13.7;
torch 2.14.1+cu126; timestral at upstream commit `a534bdb`.

## M2 forecasting research laboratory (2026-11-03, in review)

`mpe research` runs walk-forward experiments (method: `docs/M2_RESEARCH_METHODOLOGY.md`). Results
live in `data/research.sqlite3`; the market database is opened read-only. Reports are committed
under `reports/experiments/`. All real experiments below ran on a read-only snapshot of the live
database taken 2026-11-03 at about 11:38 UTC.

**Every real result is reconstructed research.** All stored data was retrieved on 2026-11-03, so
strict replay of earlier cutoffs is empty. The strict experiments `stocks-1434f4f6e825` (1,840
origins) and `polymarket-39b8a053a14d` (11,026 origins) found no usable origin, which is correct.

| experiment | domain | origins (usable) | scored cases per model | runtime |
|---|---|---|---|---|
| `stocks-4daa0990200b` | 10 XNYS assets, every session 2012-03-01 to 2026-09-29, h = 1/5/20 | 36,650 | 109,950 | ~1 h 45 min |
| `polymarket-cd414105d4c8` | 46 of 47 panel markets (YES price, logit), every 6 h 2025-06-01 to 2026-11-01, h = 1/6/24 h | 38,623 (5,433 excluded) | 113,072 | ~3 h 20 min |
| `stocks-d35cd4ace9ec` | CPU check: SPY, four Timestral sizes on CPU | 83 | 249 | 1 min |

No forecast failed in any run (0 of 677,000+).

### Stocks: no point-forecast edge, a small interval edge

- **Median forecasts:** every Timestral size is within ±0.35% of the zero-return benchmark on MAE at
  every horizon. Most comparisons show `no demonstrated difference`. The few labelled `better`
  (209M, +0.1–0.2%) have Holm-adjusted Diebold-Mariano p-values above 0.6. **Timestral has not shown
  that it predicts daily returns.**
- **Probabilistic forecasts:** CRPS_q improves on `zero` by 0.9–1.7% at 1 session, 0.5–0.9% at 5 and
  0.2–0.5% at 20 sessions. Most comparisons are significant after the Holm adjustment, the
  per-asset skill average agrees (so it is not driven by volatile assets), and at 1 session
  123M and 209M are better on all 10 assets. 90% intervals cover 89–90% for every model.
  This edge is small and has not been tested against a volatility model (EWMA/GARCH).
- **Size:** larger is slightly better on CRPS (209M ≥ 123M > 28M > 5M), by tenths of a percent.
- **Baselines:** none beats `zero`; `persistence` and `momentum` are 45–150% worse on CRPS.

### Polymarket: worse than the last price at 1 hour, better intervals at 6 and 24 hours

- **1 hour:** Timestral is worse than the `persistence` baseline on MAE (4.8% for 209M to 11.6% for
  5M) and no better on CRPS.
- **6 and 24 hours:** CRPS_q is 2.6–2.8% (6 h) and 4.4–4.5% (24 h) better than `persistence` for
  28M–209M, with 18–23 of 46 markets `better` and at most 1 `worse` at 6 h. 90% coverage is
  88–89% against persistence's 84% at 24 h.
- **Median at 24 h:** 1.9% better than the `persistence` baseline (Holm p ≈ 0.03–0.04). Caution: the
  M0 persistence baseline adds the median of its own past errors, so it is not exactly the last
  price; an interim check against the literal last price had Timestral's median about 1.5% *worse*
  at 24 h. The interval advantage is the more robust finding.
- **Resolution analysis:** 12 resolved markets, 11 scored. Too few for any calibration claim.
- **Sample:** 46 markets (one had no usable origin); 3,105 origins lacked their own sample at the
  cutoff, 1,648 had too short a history and 680 too many gaps. High-volume binary markets only.

### Conclusions for the five M2 questions

1. Timestral does **not** beat simple baselines at predicting the median price or return. It gives
   slightly better-calibrated, sharper uncertainty: about 1% on stocks and 3–4% on Polymarket at
   6–24 hours.
2. Larger models are marginally better, by much less than the gap between sizes would suggest; 5M is clearly weakest on Polymarket.
3. Its quantiles are well calibrated on stocks and as good as or better than the baselines' on
   Polymarket.
4. Polymarket differs: worse than the last price at 1 hour, better intervals at longer horizons.
5. Stock interval gains hold on most assets; per-year tables are in the report. Polymarket gains
   hold on about 40–50% of markets and are inconclusive on the rest.

Nothing here supports a directional trading signal.

### Hardware (GTX 1060 Max-Q, fp32, one series per call, context 512 / 336)

| model | ms per forecast (stocks, GPU) | peak RSS | peak VRAM |
|---|---|---|---|
| timestral-5m | 20.1 | 1.70 GB | 28 MB |
| timestral-28m | 25.5 | 1.76 GB | 115 MB |
| timestral-123m | 38.0 | 1.78 GB | 481 MB |
| timestral-209m | 44.8 | 2.22 GB | 813 MB |
| baselines | 3.0–16.7 (CPU) | 1.70 GB | – |

Models were loaded one at a time and released after each run. CPU execution of all four sizes was
checked separately. Batching was measured (3.5× faster on CPU for 16 series) but not adopted,
because its output is not bit-identical; see `KNOWN_LIMITATIONS.md`.

Tests: 180 offline tests pass (48 new for M2), with 5 weights/GPU tests deselected by default.

## M1.1 (2026-11-03, merged)

- Two separate history read paths. `get_history` is strict point-in-time replay, unchanged and
  still the default. The new `replay.get_reconstructed_history` reads backfilled data under
  documented per-source availability rules, labels each row `captured` or `reconstructed`, and
  never lets a later correction reach an earlier cutoff. Details are in `DATA_SOURCES.md`, under
  "Reading history".
- Stock forecasting inputs use `close` explicitly (`STOCK_PRICE_FIELD`, `price_series`,
  `stock_log_returns`). `adj_close` is still stored. The M0 demo and sanity scripts now use
  `close`.
- `mpe ingest` always finalises its `job_runs` row. Provider construction is inside the protected
  block. Each cleanup step (budget flush, client close, raw dump close) runs even if an earlier
  one fails. A cleanup failure marks the job `failed`, and a failure to finalise never hides the
  original exception.
- No schema change and no migration. Existing rows are untouched.
- Tests: 132 offline tests pass (27 new), with 5 weights/GPU tests deselected by default.

## What works (M1, 2026-11-03)

- `uv run mpe db init`: Alembic migration `0001` creates the full §7.2 schema in
  `data/mpe.sqlite3` (WAL, foreign keys on). Prices, sizes and fees are `DecimalText` (TEXT
  affinity, tested); timestamps are UTC ISO text. `BEFORE UPDATE/DELETE` triggers make
  `forecasts`, `signals`, `orders` and `fills` immutable; `orders.is_paper = 1` is a CHECK.
- `uv run mpe ingest backfill` on the laptop (one run, about 15 minutes, ~1,900 Polymarket
  requests):
  - Watchlist SPY, QQQ, IWM, GLD, TLT, NVDA, MSFT, AAPL, AMZN, ^VIX from 2010-01-04 (4,234
    sessions each) and GBP/USD from 2010-01-02: 46,724 daily bars with adjusted close,
    dividends and splits.
  - Polymarket: 1,200 markets scanned and stored with `selection_reason`; 47 selected (35 open,
    12 resolved: 7 YES, 5 NO), each with YES/NO token assets, 506,313 hourly price points,
    59,056 hourly trade-volume rows, 70 order-book snapshots and 12 `resolutions` rows.
  - 94 data-quality events (64 history gaps, 29 large moves, 1 FX OHLC inconsistency summary).
- Idempotency, live: re-running the stock backfill gave 0 inserted / 46,724 unchanged / 0
  corrected; an incremental Polymarket update right after (345 requests) inserted 98 new hourly
  rows and corrected nothing.
- `uv run mpe ingest update`: incremental for both categories, one `job_runs` row per slot (a
  second run in the same slot is skipped). `deploy/install_user_timers.sh --enable` installs
  systemd user timers: Polymarket every 30 min, stocks after each US close.
- `uv run mpe data health [--json]`: rows, first/last bar, staleness per asset, quality events and
  recent jobs.
- Point-in-time accessor `get_history(asset_id, as_of, interval)` (tested with planted future
  bars and later corrections). M1.1 added a separate reconstructed accessor (see above).

## M1 acceptance criteria

| Criterion | Result |
|---|---|
| Both categories ingested; 10-instrument watchlist from 2010; 20–50 PM binary markets with token ids and history, ≥ 5 resolved | Pass: 10 + GBP/USD from 2010; 47 markets, 12 resolved |
| Repeated ingestion idempotent | Pass (tests, and live re-run above) |
| Injected failures (timeout, 429, malformed JSON) leave the DB unchanged | Pass: per-unit transactions; tested for a full outage, for one failing route, and for Yahoo |
| Corrections create a new `version`; old rows untouched | Pass (tests; Yahoo `adj_close` last-digit noise is ignored, see DATA_SOURCES) |
| Validation tests with mocked providers / recorded fixtures; no live API by default | Pass: 105 offline tests (52 new) |
| `docs/DATA_SOURCES.md` documents endpoints, limits, licensing, gaps | Pass |

Guard test `test_clock_injection` added: nothing in `src/` reads the wall clock except `clock.py`.

## What works (M0)

- `uv sync`, then `uv run pytest`: 53 tests pass offline with no GPU and no weights.
  `uv run pytest -m "weights or gpu"`: 5 more pass (each size on CPU, GPU vs CPU, VRAM released).
- `uv run python scripts/download_models.py`: all four sizes downloaded with licence and model card;
  sizes match the brief within 1% (20.8 / 111.3 / 490.4 / 837.3 MB); revisions in
  `data/models/manifest.json`.
- `uv run python scripts/m0_demo.py`: all four Timestral sizes and five baselines forecast SPY log
  returns (h = 1, 5, 20) and the Polymarket logit YES price (h = 1, 6, 24) on CPU and on the GPU.
  Every output passes `validate_output` (shapes, finite, non-decreasing quantiles) and every
  inverse-logit probability is strictly inside (0, 1).
- `ForecastModel` interface (`src/mpe/models/base.py`) with input validation, leakage check against
  `input_cutoff`, context truncation, quantile interpolation; Timestral adapter; baselines `zero`,
  `persistence`, `moving_average`, `momentum`, `linear_trend` with empirical-error quantiles;
  `ModelManager` with LRU unloading (`max_resident` default 1); transforms (log returns, price
  reconstruction, logit/inverse logit with ε clipping).
- Guard tests: `timestral` is imported only in `src/mpe/models/timestral.py`; no trading or wallet
  clients and no order endpoints anywhere in `src/` or `scripts/`. There is no trading code.

## M0 acceptance criteria

| Criterion | Result |
|---|---|
| `uv sync` + `uv run pytest` pass clean, no GPU/network | Pass (weights/gpu/network tests skipped by marker) |
| Download all four; sizes within 1% | Pass |
| Timestral inference works; demo runs to completion | Pass |
| All four sizes on CPU | Pass |
| GPU inference on the GTX 1060 | Pass (sm_60 kernels on sm_61; see `docs/MODELS.md`) |
| Outputs valid (shapes, finite, monotone quantiles, probabilities in (0, 1)) | Pass |
| Determinism: identical CPU output; GPU within 1e-5 | Pass: CPU and GPU repeats bit-identical; GPU vs CPU ≤ 1.2e-6 |
| Load → forecast → unload all sizes in sequence under 8 GB, memory released | Pass: peak RSS 2.1 GB (CPU) / 2.9 GB (GPU); RSS back to baseline, VRAM allocated 0 after each unload |
| Benchmarks in `benchmarks/` and summarised here | Pass |
| Tests: validation, output structure, quantiles, transforms, leakage | Pass |
| `timestral` imported only in the adapter (tested) | Pass |
| `docs/MODELS.md`, `docs/STATUS.md`, `docs/KNOWN_LIMITATIONS.md` exist | Pass |
| No trading code | Pass |

## Benchmark summary

Full table: `benchmarks/m0_create_2026-11-03.md` (JSON alongside). Batch 1, univariate,
symmetric averaging on (two forward passes per forecast), fp32, 10 warm runs per cell, p50 in ms:

| size | load s (cpu / gpu) | cpu ctx 512 | cpu ctx 2048 | cpu ctx 8192 | gpu ctx 512 | gpu ctx 2048 | gpu ctx 8192 | peak VRAM (8192) |
|---|---|---|---|---|---|---|---|---|
| 5M | 0.17 / 0.35 | 18 | 25 | 92 | 19 | 18 | 19 | 31 MB |
| 28M | 0.31 / 0.45 | 37 | 67 | 243 | 24 | 25 | 37 | 122 MB |
| 123M | 0.92 / 1.27 | 102 | 248 | 783 | 38 | 44 | 108 | 492 MB |
| 209M | 1.61 / 2.14 | 165 | 381 | 1,171 | 47 | 71 | 164 | 825 MB |

(h = 1; h = 96 adds roughly 5–15%.) Peak process RSS: 1.37 GB for 209M on CPU; about 1.3 GB on
GPU for any size, most of it the CUDA runtime. Nothing ran out of memory. The first GPU forecast
in a process takes ~1.5 s extra (lazy kernel loading).

Takeaways: every size fits comfortably in 8 GB RAM and 6 GB VRAM at these contexts. The GPU is
7× faster for 209M at 8,192 steps; for 5M the CPU is as fast at short contexts. Even 209M on CPU
does a forecast in about 1 s at 8,192 steps, so CPU-only operation is viable for M2 if the GPU
becomes unavailable. fp16 on the 1060 is 2× slower than fp32 (151 vs 76 ms, 209M, ctx 2048), as
expected on Pascal, so we stay on fp32.

### Optional sanity check (report only, no conclusions)

`uv run python scripts/m0_sanity.py`: rolling one-step forecasts of SPY daily log returns over
the last 250 days of the fixture (2025-11-04 to 2026-11-02). These M0 figures were computed from
`adj_close`. Since M1.1 the script uses `close`, and on that series `zero` gives MAE 0.00625 and
directional accuracy 0.512 (rerun on 2026-11-03, baselines only):

| model | MAE | directional accuracy | mean pinball loss |
|---|---|---|---|
| timestral-5m | 0.00626 | 0.516 | 0.002150 |
| timestral-209m | 0.00623 | 0.516 | 0.002144 |
| zero (random walk on price) | 0.00625 | 0.516 | 0.002151 |
| persistence (last return) | 0.00897 | 0.508 | 0.003070 |

n = 250, no significance testing. Timestral and the zero baseline are indistinguishable here,
which is what one would expect for daily index returns. This says nothing yet about the research
questions; M2 does the real evaluation.

## Outstanding issues / next steps

- Review and merge M2. Possible follow-ups (not done): an EWMA/GARCH volatility baseline to test
  whether Timestral's interval edge is more than volatility clustering; strict experiments once the
  timers have collected months of forward data.
- Possible data follow-ups: category quotas for the Polymarket panel; Data API v2 3-hour history
  as a fallback; an Alpha Vantage cross-check if Yahoo degrades.
- See `docs/KNOWN_LIMITATIONS.md`.
