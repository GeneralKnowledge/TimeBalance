# Status

_Last updated 2026-11-03._

## Milestones

| Milestone | State |
|---|---|
| M0 Foundation and Timestral integration | Done (PR #2, merged) |
| M1 Data ingestion and persistence | Done, pending review (branch `milestone/m1-data`) |
| M2–M5 | Not started |

## Environment (laptop `create`)

Ubuntu, kernel 6.8; Intel i7-8750H (6 cores / 12 threads); 7.6 GB RAM + 4 GB swap; NVIDIA GTX 1060
Max-Q 6 GB (compute capability 6.1), driver 550.163.01 (CUDA 12.4); Python 3.12.3; uv 0.13.7;
torch 2.14.1+cu126; timestral at upstream commit `a534bdb`.

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
  bars and later corrections).

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
the last 250 days of the fixture (2025-11-04 to 2026-11-02):

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

- Review and merge M1.
- M2: read history only through `get_history`; build hourly Polymarket series and daily return
  series from it; trading-calendar-aware target timestamps.
- Possible data follow-ups: category quotas for the Polymarket panel; Data API v2 3-hour history
  as a fallback; an Alpha Vantage cross-check if Yahoo degrades.
- Batch API (many series per call) is available upstream but the adapter sends one series per
  call; add batching in M2 when walk-forward runs need throughput.
- See `docs/KNOWN_LIMITATIONS.md`.
