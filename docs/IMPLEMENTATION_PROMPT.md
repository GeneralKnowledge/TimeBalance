# Market Prediction Engine: Implementation Brief and Coding-Agent Instructions

> **How to use this document.** Give it to the coding agent as its task brief. It is addressed to
> the agent. Work strictly milestone by milestone. **The first task is M0 only (§14).** Do not
> start M1 until every M0 acceptance criterion passes or has a documented, specific blocker.
>
> Sources: the owner's architecture plan and implementation brief (2026-11-03), plus upstream
> facts checked on 2026-11-03 (§3.1). Items marked **⚠️ UNVERIFIED** must be checked against
> upstream source code before you build on them.

---

## 1. Mission

Build a local-first, autonomous financial market prediction and paper-trading research platform.

The project investigates whether small pretrained time-series foundation models, particularly
Mistral's **Timestral**, can identify predictive signals in:

1. Traditional financial markets (stocks, ETFs and optionally cryptocurrency).
2. Prediction markets (initially Polymarket).

The objective is to evaluate forecasting accuracy, identify potential market mispricing and test
trading strategies through simulated paper trading. The system operates autonomously: it
collects market data, generates forecasts, evaluates opportunities, executes simulated trades and
records results.

**This is an experimental research project. It must never execute real-money trades.**
The most important objective is scientific validity, not impressive-looking profitability. A
rigorous result that Timestral has no advantage over a random walk is a successful outcome.

### Five research questions

1. Can Timestral predict financial time-series movements better than simple baselines?
2. Can it identify market mispricing?
3. Does combining several forecasting methods improve performance?
4. Can the system generate profitable paper trades after realistic costs?
5. Which model sizes, assets and forecasting horizons work best?

### Non-negotiable rules

1. **Paper trading only.** No code path may place a real order. Do not add any exchange SDK,
   wallet, private key, broker API, or authenticated trading endpoint. Never request or store
   trading credentials. Enforced by tests (§11).
2. **Models are plugins.** Only `src/mpe/models/timestral.py` may import `timestral`. Everything
   else talks to the `ForecastModel` interface (§8, M0).
3. **Immutable records.** Forecasts, signals, orders and fills are never updated or deleted after
   being written. Later data corrections create new rows; they never rewrite history.
4. **No look-ahead.** Every feature, forecast and signal uses only data whose `available_at` is at
   or before the decision time (`input_cutoff`). All history reads go through one point-in-time
   accessor.
5. **Record everything.** Every forecast is stored whether or not it leads to a trade. Every signal
   records why a trade was or wasn't taken.
6. **Separate forecasting accuracy, probability accuracy and trading profitability** (§9).

---

## 2. Fixed user requirements

Treat these as fixed unless an implementation constraint requires discussion with the owner.

| Requirement | Decision |
|---|---|
| Markets | Stocks and prediction markets |
| Operation | Fully autonomous |
| Execution | Paper trading only |
| Initial balance | £1,000 virtual |
| Primary model | Timestral |
| Model sizes | 5M, 28M, 123M, 209M |
| Training | Zero-shot initially |
| Hardware | Local Ubuntu machine |
| GPU | NVIDIA GTX 1060, 6 GB VRAM |
| RAM | 8 GB system RAM |
| Storage | SQLite |
| Dashboard | Local web application |
| Deployment | Ubuntu / systemd |
| Budget | Free or extremely low cost |
| Containers | Avoid Docker unless genuinely necessary |

Design for constrained hardware. **Do not assume all four models can stay loaded at once.**
Default to one resident model at a time, loaded and unloaded on demand.

---

## 3. Initial research requirements

Before implementing each integration, inspect the current upstream projects and documentation.
Do not invent APIs or assume a Hugging Face interface works without checking the implementation.
Record findings in the docs listed in §12.

### 3.1 Timestral: what has been verified (2026-11-03)

Timestral is a real, publicly released family of time-series foundation models from Mistral AI
(Timestral 1.0, status "Public Preview"). Checked against the Hugging Face model cards and file
listings, the licence file and Mistral's docs page.

| Size | Hugging Face repo | Weights (FP32 safetensors) | Notes from card |
|---|---|---|---|
| 5M | `mistralai/Timestral-5M` | 20.8 MB | 5.21M params, 8 layers, embedding 192 |
| 28M | `mistralai/Timestral-28M` | 111 MB | card not yet reviewed |
| 123M | `mistralai/Timestral-123M` | 490 MB | card not yet reviewed |
| 209M | `mistralai/Timestral-209M` | 837 MB | 24 layers, embedding 768 |

- **Upstream code:** https://github.com/mistralai/timestral
- **Install:** `pip install git+https://github.com/mistralai/timestral.git` (Python ≥ 3.10,
  torch ≥ 2.4), or clone and `uv sync --frozen`. There is no official PyPI package. A third-party
  wrapper (`timecopilot-timestral`) exists on PyPI: **do not use it**.
- **Documented API (from the model card):**
  ```python
  import numpy as np, torch
  from timestral import TimestralForecaster

  model = TimestralForecaster.from_pretrained(
      "mistralai/Timestral-209M",
      device="cuda" if torch.cuda.is_available() else "cpu",
  )
  context = np.random.default_rng(42).standard_normal(1000).cumsum()
  forecast = model.forecast(context, prediction_length=96)
  median = forecast.median
  lower, upper = forecast.quantile(0.1), forecast.quantile(0.9)
  ```
- **Output:** 21 quantile levels, 0.01, 0.05, 0.10 … 0.90, 0.95, 0.99. The card elides the middle
  levels; the 0.05 step is inferred.
- **Limits:** max context 32,768 steps (1,024 patches × 32); max single-pass horizon 1,024 steps.
  Longer horizons are produced block by block with each block's median appended to the context.
- **Missing values:** NaN marks missing values in the context.
- **Inputs:** univariate or multivariate targets; past-only and known-future covariates, numeric
  or categorical (categorical is target-encoded). No call signature is shown for these.
- **Licence:** "Modified MIT". Rights do not apply to any company (or employer) with global
  monthly revenue above US$20M; this personal research project is fine. Keep the attribution and
  licence notice with any copy of the weights.
- **Hardware:** CPU or GPU through PyTorch. No published memory or latency figures; M0 measures them.
  Raw weights are small enough for 8 GB RAM even at 209M (837 MB), but runtime memory at long
  contexts is unknown.

### 3.2 Timestral: ⚠️ UNVERIFIED, resolve in M0 from upstream source

Write the answers, with file/line references and the upstream commit SHA, to `docs/MODELS.md`.

- Official architecture details for the 28M and 123M sizes.
- Exact call signature and array layout for **multivariate** targets.
- Exact call signature for **past-only** and **known-future covariates**.
- Whether `forecast.quantile(q)` accepts any q or only the 21 trained levels; exact level list.
- Whether a batch API exists (many series per call), and return shapes for multivariate output.
- Whether a frequency / sampling-interval argument exists (none is documented).
- Determinism: any sampling or randomness in inference; how to seed it.
- Load/unload behaviour: does `from_pretrained` cache, and does deleting the object plus
  `torch.cuda.empty_cache()` release VRAM fully?
- **GTX 1060 compatibility.** The GTX 1060 is Pascal (compute capability 6.1). Recent PyTorch
  CUDA wheels have been dropping older GPU architectures. Check whether the torch build `uv`
  resolves still includes `sm_61` (`torch.cuda.get_arch_list()`). If not, find a torch ≥ 2.4 +
  CUDA wheel that does and pin it. If none works, run CPU-only and document it as a specific
  blocker. Also check fp16 behaviour on Pascal (slow; prefer fp32).
- Peak RAM and VRAM per size at context lengths 512 / 2,048 / 8,192 (measured in M0).

### 3.3 Polymarket (research in M1, before writing the provider)

Read https://docs.polymarket.com/ and document in `docs/DATA_SOURCES.md`:
Gamma API (market and event discovery, metadata, YES/NO token ids), CLOB API (prices, order
books, `prices-history`), Data API (trades, activity), fees and trading constraints, resolution
data, rate limits and pagination. **Read-only, unauthenticated endpoints only.**

### 3.4 Stock data (research in M1)

Document availability, licensing/terms, limitations and rate limits for **yfinance** (unofficial
Yahoo scraping; terms restrict use to personal research), **Alpha Vantage** (free tier 25
requests/day; real-time and 15-minute-delayed US data are paid), and **Stooq** (free daily CSVs).
Start with yfinance; add the others only where useful.

---

## 4. Architecture

```
Data Providers → Data Normalisation → Historical Database → Feature Engineering
  → Forecasting Laboratory → Prediction and Signal Engine → Risk Management
  → Paper Trading Simulator → Evaluation and Reporting → Dashboard
```

All components have clear interfaces. Timestral is replaceable: forecasting logic is not coupled
to trading, ingestion or the dashboard. Data sources sit behind a provider abstraction. Timestral
and baselines share one forecasting interface. The forecasting model never executes trades; its
output feeds a separate decision engine.

Market-specific notes:
- **Stocks:** forecast log returns `r_t = ln(P_t / P_{t-1})` primarily, reconstruct prices from them.
- **Prediction markets:** forecast the YES price in logit space `z = ln(p / (1 − p))`, with `p`
  clipped to `[ε, 1 − ε]` (ε configurable, default 1e-4). A forecast of the future token
  **price** is not the probability the event **resolves** YES; keep them as separate targets.
- **Multivariate:** respect targets vs covariates. Volume and spread can inform a price forecast
  as **past-only** covariates; they must never be passed as known-future inputs. Calendar
  features are the main legitimate known-future covariates.

---

## 5. Technology stack

Python 3.11+, PyTorch, official Timestral implementation, NumPy, Pandas, SQLAlchemy 2.x
(+ Alembic for migrations), SQLite, FastAPI, Streamlit (initially), Plotly, APScheduler, Pytest,
uv. Small helpers allowed when justified: `pydantic`/`pydantic-settings` (config and API
schemas), `huggingface_hub` (weights), `psutil` (memory benchmarks), `httpx` + `respx` (HTTP and
mocks), `typer` (CLI), `structlog` or stdlib `logging` with JSON output.

Do not introduce Docker, Kubernetes, Redis, Kafka, PostgreSQL, cloud services or paid APIs unless
there is a clearly demonstrated technical requirement.

---

## 6. Repository structure

Build in this repository (`TimeBalance`). Use the owner's layout, placed under a package
directory `src/mpe/` so the project installs cleanly with `uv` and imports are unambiguous
(`from mpe.models.base import ForecastModel`).

```
TimeBalance/
├── config/{settings,assets,strategies,risk}.yaml
├── src/mpe/
│   ├── data/
│   │   ├── providers/{base,polymarket,yahoo,alphavantage,stooq}.py
│   │   ├── ingestion.py  normalisation.py  validation.py
│   ├── features/{returns,volatility,momentum,transforms,multivariate}.py
│   ├── models/{base,registry,timestral,baselines,ensemble}.py
│   ├── prediction/{forecasting,calibration,signals}.py
│   ├── trading/{portfolio,execution,positions,risk}.py
│   ├── evaluation/{backtesting,metrics,comparison}.py
│   ├── storage/{database,orm,types,repositories}.py + migrations/
│   ├── scheduler/jobs.py
│   ├── api/                 # FastAPI app (M4)
│   ├── clock.py             # injectable clock; nothing else calls datetime.now()
│   ├── config.py
│   └── main.py              # CLI entry point `mpe`
├── dashboard/               # Streamlit, reads the FastAPI API only (M4)
├── scripts/                 # download_models.py, m0_demo.py, m0_benchmark.py
├── tests/{unit,integration,fixtures}/
├── data/                    # gitignored: SQLite DB, model cache, raw dumps
├── benchmarks/              # committed benchmark results (JSON + markdown)
├── deploy/                  # systemd units (M4)
├── docs/
├── pyproject.toml  uv.lock  README.md
```

---

## 7. Database design (SQLite + SQLAlchemy)

### 7.1 Conventions

- `PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;` Migrations via Alembic.
- **Timestamps:** UTC, ISO-8601 `TEXT` (`2026-11-03T09:30:00Z`).
- **Money and prices: no binary floats in accounting.** SQLite has no native decimal type, so use a
  custom SQLAlchemy `TypeDecorator` (`storage/types.py: DecimalText`) that stores Python
  `Decimal` as canonical `TEXT` and returns `Decimal`. Use it for every price, quantity, cash,
  fee, slippage and P&L column (marked `DEC` below). `DEC` is shorthand in this document only:
  in the real DDL the column must have TEXT affinity, because SQLite would give a literal `DEC`
  type NUMERIC affinity and silently convert values to floats. Arithmetic in `trading/` uses `Decimal` with
  an explicit context; rounding to pence happens only at defined points (fills, snapshots).
  Model outputs (forecast values, quantiles, metrics) are statistics and may be `REAL`.
- **Structured forecast output:** JSON `TEXT`, validated by a pydantic schema, with a
  `schema_version` key.
- **Provenance on every observation:** `source`, `source_ts`, `retrieved_at`, `available_at`, `version`.
- **Immutability:** `BEFORE UPDATE` / `BEFORE DELETE` triggers raising `ABORT` on `forecasts`,
  `signals`, `orders` and `fills`. Order status changes are recorded as new rows in
  `order_events`, so `orders` itself stays append-only.

### 7.2 Schema (DDL to implement; adjust only with a documented reason)

```sql
CREATE TABLE assets (
  id            INTEGER PRIMARY KEY,
  symbol        TEXT NOT NULL,             -- 'SPY', 'BTC-USD', or Polymarket token id
  name          TEXT,
  asset_type    TEXT NOT NULL CHECK (asset_type IN ('stock','etf','crypto','fx','index','pm_token')),
  exchange      TEXT,
  currency      TEXT NOT NULL DEFAULT 'USD',
  provider      TEXT NOT NULL,             -- 'yfinance','polymarket',...
  market_id     INTEGER REFERENCES markets(id),   -- pm_token only
  outcome_side  TEXT CHECK (outcome_side IN ('YES','NO') OR outcome_side IS NULL),
  active        INTEGER NOT NULL DEFAULT 1,
  listed_at     TEXT, delisted_at TEXT,    -- keep delisted assets (survivorship)
  meta_json     TEXT,
  UNIQUE (provider, symbol)
);

CREATE TABLE markets (                       -- prediction markets
  id                 INTEGER PRIMARY KEY,
  provider           TEXT NOT NULL DEFAULT 'polymarket',
  provider_market_id TEXT NOT NULL,          -- condition id
  slug               TEXT,
  question           TEXT NOT NULL,
  description        TEXT,
  market_type        TEXT NOT NULL,          -- 'binary' initially
  category           TEXT,
  yes_token_id       TEXT, no_token_id TEXT,
  resolution_rules   TEXT, resolution_source TEXT,
  opening_time       TEXT, closing_time TEXT,
  resolution_status  TEXT NOT NULL CHECK (resolution_status IN
                       ('open','closed','resolved','cancelled','disputed','ambiguous')),
  resolution_value   TEXT,                   -- 'YES','NO','INVALID','SPLIT' or NULL
  fee_bps            DEC,
  selection_reason   TEXT,                   -- why included/excluded
  raw_json           TEXT,                   -- raw source payload
  UNIQUE (provider, provider_market_id)
);

CREATE TABLE observations (
  id            INTEGER PRIMARY KEY,
  asset_id      INTEGER NOT NULL REFERENCES assets(id),
  timestamp     TEXT NOT NULL,               -- bar close / snapshot time
  interval      TEXT NOT NULL,               -- '1d','1h','15m','snapshot'
  open DEC, high DEC, low DEC, close DEC, adj_close DEC,
  volume        DEC,
  bid DEC, ask DEC, bid_size DEC, ask_size DEC,
  liquidity     DEC,
  source        TEXT NOT NULL,
  source_ts     TEXT,                        -- time reported by the source
  retrieved_at  TEXT NOT NULL,               -- when we fetched it
  available_at  TEXT NOT NULL,               -- earliest time it could have been known
  version       INTEGER NOT NULL DEFAULT 1,  -- corrections append a new version
  quality_flags TEXT,                        -- JSON list
  UNIQUE (asset_id, timestamp, interval, source, version)
);
CREATE INDEX ix_obs_asset_time ON observations(asset_id, interval, timestamp);

CREATE TABLE order_book_snapshots (          -- Polymarket depth, for execution simulation
  id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL REFERENCES assets(id),
  timestamp TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  bids_json TEXT NOT NULL, asks_json TEXT NOT NULL   -- [["0.53","120.0"], ...] decimal strings
);
CREATE INDEX ix_book_asset_time ON order_book_snapshots(asset_id, timestamp);

CREATE TABLE features (
  id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL REFERENCES assets(id),
  timestamp TEXT NOT NULL, available_at TEXT NOT NULL,
  feature_name TEXT NOT NULL, feature_value REAL,
  feature_version TEXT NOT NULL,
  UNIQUE (asset_id, timestamp, feature_name, feature_version)
);

CREATE TABLE experiments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL, config_json TEXT NOT NULL, config_hash TEXT NOT NULL,
  created_at TEXT NOT NULL, notes TEXT
);

CREATE TABLE model_runs (
  id               INTEGER PRIMARY KEY,
  experiment_id    INTEGER REFERENCES experiments(id),
  model_name       TEXT NOT NULL,            -- 'timestral','random_walk',...
  model_size       TEXT,                     -- '5M','28M','123M','209M'
  model_version    TEXT NOT NULL,            -- HF revision SHA / code version
  code_version     TEXT NOT NULL,            -- git SHA of this repo
  configuration    TEXT NOT NULL,            -- JSON
  mode             TEXT NOT NULL CHECK (mode IN ('live','backtest','holdout','benchmark')),
  inference_device TEXT,
  started_at TEXT NOT NULL, completed_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed')),
  error TEXT, peak_ram_mb REAL, peak_vram_mb REAL
);

CREATE TABLE forecasts (                     -- IMMUTABLE
  id                     INTEGER PRIMARY KEY,
  model_run_id           INTEGER NOT NULL REFERENCES model_runs(id),
  asset_id               INTEGER NOT NULL REFERENCES assets(id),
  forecast_type          TEXT NOT NULL,      -- 'log_return','logit_yes_price','volume','realised_vol',...
  created_at             TEXT NOT NULL,      -- wall-clock write time
  input_cutoff_timestamp TEXT NOT NULL,      -- information cutoff (as_of)
  target_timestamp       TEXT NOT NULL,
  horizon                INTEGER NOT NULL,
  horizon_unit           TEXT NOT NULL,      -- 'trading_day','hour'
  forecast_values        TEXT NOT NULL,      -- JSON {"median":..,"mean":..,"implied_price":{...}}
  quantiles              TEXT NOT NULL,      -- JSON {"0.01":..,...,"0.99":..}
  context_length         INTEGER NOT NULL,
  context_start_timestamp TEXT NOT NULL,
  input_hash             TEXT NOT NULL,      -- hash of exact inputs and covariates
  feature_version        TEXT,
  multivariate_group     TEXT,               -- links joint forecasts
  runtime_ms             REAL,
  UNIQUE (model_run_id, asset_id, forecast_type, input_cutoff_timestamp, horizon)
);
CREATE INDEX ix_fc_target ON forecasts(asset_id, forecast_type, horizon, target_timestamp);

CREATE TABLE signals (                       -- IMMUTABLE; includes skipped opportunities
  id INTEGER PRIMARY KEY,
  forecast_id      INTEGER NOT NULL REFERENCES forecasts(id),   -- primary forecast
  forecast_ids_json TEXT NOT NULL,           -- all forecasts considered
  asset_id         INTEGER NOT NULL REFERENCES assets(id),
  strategy_name    TEXT NOT NULL,
  direction        TEXT CHECK (direction IN ('buy','sell','none')),
  reference_price  DEC NOT NULL,             -- executable price (ask for buys, bid for sells)
  expected_return  REAL, estimated_cost REAL, expected_net_return REAL,
  confidence       REAL,
  decision         TEXT NOT NULL CHECK (decision IN ('open','close','hold','skip')),
  reasons_json     TEXT NOT NULL,            -- every rule evaluated and its result
  created_at       TEXT NOT NULL
);

CREATE TABLE orders (                        -- IMMUTABLE; status via order_events
  id INTEGER PRIMARY KEY,
  signal_id       INTEGER REFERENCES signals(id),
  asset_id        INTEGER NOT NULL REFERENCES assets(id),
  side            TEXT NOT NULL CHECK (side IN ('buy','sell')),
  order_type      TEXT NOT NULL CHECK (order_type IN ('market','limit')),
  requested_price DEC, quantity DEC NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,      -- duplicate-order prevention
  is_paper        INTEGER NOT NULL DEFAULT 1 CHECK (is_paper = 1),
  created_at      TEXT NOT NULL
);
CREATE TABLE order_events (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  status TEXT NOT NULL CHECK (status IN ('pending','partial','filled','cancelled','rejected','expired')),
  reason TEXT, created_at TEXT NOT NULL
);

CREATE TABLE fills (                         -- IMMUTABLE
  id INTEGER PRIMARY KEY,
  order_id          INTEGER NOT NULL REFERENCES orders(id),
  executed_price    DEC NOT NULL,            -- native currency
  executed_quantity DEC NOT NULL,
  fx_rate_to_gbp    DEC NOT NULL,
  fees              DEC NOT NULL DEFAULT '0',   -- GBP
  slippage          DEC NOT NULL DEFAULT '0',   -- GBP
  liquidity_source  TEXT,                    -- 'book_snapshot:<id>' | 'next_open:<obs id>'
  executed_at       TEXT NOT NULL
);

CREATE TABLE positions (
  id INTEGER PRIMARY KEY,
  asset_id            INTEGER NOT NULL REFERENCES assets(id),
  strategy_name       TEXT NOT NULL,
  quantity            DEC NOT NULL,
  average_entry_price DEC NOT NULL,          -- GBP
  current_value       DEC, realised_pnl DEC NOT NULL DEFAULT '0', unrealised_pnl DEC,
  status              TEXT NOT NULL CHECK (status IN ('open','closed','settled')),
  exit_reason         TEXT,
  opened_at TEXT NOT NULL, closed_at TEXT
);  -- derived state; rebuildable from fills (test this)

CREATE TABLE portfolio_snapshots (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('live','backtest')),
  cash DEC NOT NULL, positions_value DEC NOT NULL, total_equity DEC NOT NULL,
  exposure DEC NOT NULL, open_positions INTEGER NOT NULL,
  realised_pnl DEC NOT NULL, unrealised_pnl DEC NOT NULL,
  drawdown REAL NOT NULL
);

CREATE TABLE resolutions (
  id INTEGER PRIMARY KEY,
  market_id INTEGER NOT NULL UNIQUE REFERENCES markets(id),
  resolved_at TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('YES','NO','INVALID','SPLIT','CANCELLED')),
  source TEXT, retrieved_at TEXT NOT NULL, raw_json TEXT
);

CREATE TABLE evaluations (                   -- one row per forecast once the target is observed
  id INTEGER PRIMARY KEY,
  forecast_id        INTEGER NOT NULL REFERENCES forecasts(id),
  evaluated_at       TEXT NOT NULL,
  actual_value       REAL NOT NULL,
  actual_observation_id INTEGER REFERENCES observations(id),
  error REAL, absolute_error REAL, squared_error REAL,
  direction_correct  INTEGER,
  pinball_loss       REAL,                   -- mean over quantile levels
  crps               REAL,
  in_80_interval     INTEGER, in_98_interval INTEGER,
  evaluation_version TEXT NOT NULL,
  UNIQUE (forecast_id, evaluation_version)
);

CREATE TABLE evaluation_summaries (          -- aggregated comparison results
  id INTEGER PRIMARY KEY,
  computed_at TEXT NOT NULL, evaluation_version TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('model','strategy')),
  model_name TEXT, model_size TEXT, strategy_name TEXT,
  asset_id INTEGER, horizon INTEGER, segment_json TEXT,   -- category, volatility regime...
  window_start TEXT, window_end TEXT,
  is_holdout INTEGER NOT NULL DEFAULT 0,
  metric TEXT NOT NULL, value REAL NOT NULL, n INTEGER NOT NULL,
  ci_low REAL, ci_high REAL, baseline_value REAL, p_value REAL
);

CREATE TABLE data_quality_events (
  id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
  asset_id INTEGER, source TEXT, check_name TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
  details_json TEXT
);

CREATE TABLE job_runs (
  id INTEGER PRIMARY KEY, job_name TEXT NOT NULL,
  scheduled_for TEXT, started_at TEXT NOT NULL, finished_at TEXT,
  status TEXT NOT NULL, error TEXT, stats_json TEXT,
  UNIQUE (job_name, scheduled_for)           -- no duplicate job executions after restart
);

CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
-- keys: kill_switch, drawdown_halt, last_holdout_evaluation, schema_version
```

**`available_at` rules:** daily stock bars: exchange close + configurable delay (default 30 min);
live snapshots: `retrieved_at`; backfilled Polymarket history: `timestamp` + configurable latency.
The point-in-time accessor `get_history(asset_id, series, as_of)` filters on
`available_at <= as_of` and picks the latest `version` whose `retrieved_at <= as_of` where known.

---

## 8. Milestone implementation plan

Work through milestones in order. Each milestone produces working software, tests, documentation
(updates to the §12 docs, including `docs/STATUS.md`) and a progress report, delivered as a
milestone branch and pull request.

### M0: Foundation and Timestral integration (highest priority, start here)

**Goal:** prove the central forecasting technology works on the intended hardware. No database,
data providers, dashboard or trading in M0.

Steps:

1. Inspect the repository and environment (`nvidia-smi`, driver/CUDA version, Python, free RAM/disk).
2. Read the upstream Timestral source and answer every §3.2 item in `docs/MODELS.md`.
3. Create the project with `uv`: Python ≥ 3.11, `src/mpe` layout, ruff, pytest, `.gitignore`.
   Add Timestral as a git dependency **pinned to a commit SHA**. Configure torch so the CPU path
   always works and the CUDA path targets a wheel that supports `sm_61` (§3.2).
4. `scripts/download_models.py`: `huggingface_hub.snapshot_download` for the four repos into
   `data/models/`, idempotent and resumable; writes `data/models/manifest.json` with repo id,
   revision SHA, file sizes. Keep LICENSE files alongside weights.
5. Implement the forecasting abstraction (below), the Timestral adapter, a model registry and
   the baselines: persistence/random walk, moving average, momentum, simple trend extrapolation.
6. Get **one** model working end to end (5M on CPU), then expand to 28M, 123M, 209M, then GPU.
7. Transforms in `features/transforms.py`: log returns, logit/inverse-logit with ε clipping,
   price reconstruction from cumulative returns.
8. Fixtures (committed, small, offline): ~1,500 rows of SPY daily OHLCV; one YES-price series
   (real Polymarket history if easy to fetch once, otherwise a synthetic bounded walk, labelled);
   a synthetic sine-plus-noise series with a known answer.
9. `scripts/m0_demo.py` (the working demonstration): for each model size + baselines, forecast SPY
   log returns at h = 1, 5, 20 and logit YES price at h = 1, 6, 24, print a table with median,
   q0.1, q0.9, implied price, runtime and device.
10. `scripts/m0_benchmark.py`: for each size × device (cpu, cuda if usable) × context (512, 2,048,
    8,192) × horizon (1, 20, 96): cold load time, warm inference p50/p95 over ≥ 10 runs, peak RAM
    (`psutil`), peak VRAM (`torch.cuda.max_memory_allocated`), output validity, and unload
    verification (memory returns near baseline). Catch OOM and record it as a result. Write
    `benchmarks/m0_<hostname>_<date>.json` and a markdown summary in `docs/STATUS.md`.
11. Optional sanity check (report, draw no conclusions): rolling one-step forecasts over the last
    250 SPY days, MAE / directional accuracy / pinball loss vs random walk.

#### Forecasting interface contract

```python
# src/mpe/models/base.py  (adapt to upstream reality; keep it Timestral-agnostic)
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence
import numpy as np

@dataclass(frozen=True)
class ForecastInput:
    values: np.ndarray                 # (T,) univariate or (V, T) multivariate; NaN = missing
    timestamps: np.ndarray             # (T,) datetime64[ns, UTC], strictly increasing
    series_names: Sequence[str]        # len 1 or V
    horizon: int                       # >= 1
    input_cutoff: datetime             # UTC; timestamps[-1] <= input_cutoff
    future_timestamps: np.ndarray      # (horizon,) target times (trading calendar aware)
    past_covariates: np.ndarray | None = None    # (C_p, T)   observed only up to cutoff
    future_covariates: np.ndarray | None = None  # (C_f, T + horizon)  genuinely known ahead
    covariate_names: Sequence[str] = ()
    quantile_levels: Sequence[float] | None = None   # None = model default
    seed: int = 0

@dataclass(frozen=True)
class ForecastOutput:
    values: np.ndarray                 # point forecast (median), (V, horizon)
    timestamps: np.ndarray             # (horizon,) forecast target timestamps
    quantile_levels: tuple[float, ...]
    quantiles: np.ndarray | None       # (V, horizon, Q), non-decreasing along Q
    model: "ModelMetadata"
    inference_ms: float
    device: str                        # 'cpu' | 'cuda:0'
    input_window: dict                 # {'length', 'start', 'end', 'truncated': bool}
    extra: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ModelMetadata:
    name: str                          # 'timestral-209m', 'random_walk'
    family: str                        # 'timestral' | 'baseline'
    size: str | None                   # '209M'
    version: str                       # HF revision SHA or code version
    supports_multivariate: bool
    supports_past_covariates: bool
    supports_future_covariates: bool
    max_context: int
    max_horizon: int

class ForecastModel(Protocol):
    def load(self, device: str = "auto") -> None: ...
    def forecast(self, data: ForecastInput) -> ForecastOutput: ...
    def unload(self) -> None: ...          # must release RAM/VRAM
    def metadata(self) -> ModelMetadata: ...
    @property
    def is_loaded(self) -> bool: ...
```

Rules: validate inputs (shape, monotonic timestamps, horizon range, covariate shapes, cutoff)
and raise `InvalidForecastInput`; raise `UnsupportedRequest` rather than silently dropping
covariates; truncate over-long context to the most recent `max_context` points and record it;
baselines must emit quantiles too (from empirical residuals) so probabilistic metrics compare like
with like. A `ModelManager` enforces `max_resident_models` (default 1) with LRU unloading.

#### M0 acceptance criteria

- [ ] `uv sync` then `uv run pytest` pass on a clean clone with no GPU and no network (tests needing
      weights or network are marked and skipped by default).
- [ ] `uv run python scripts/download_models.py` fetches all four models; manifest sizes match §3.1
      within 1%.
- [ ] Timestral inference works locally; `uv run python scripts/m0_demo.py` runs to completion.
- [ ] All four sizes tested on CPU, or each failure documented with a specific blocker
      (error, measured memory). Smaller models stay operational even if 209M is too demanding.
- [ ] GPU inference tested on the GTX 1060, or the specific incompatibility documented
      (torch version, `get_arch_list()` output, error text).
- [ ] Every output is valid: correct shapes, finite values, quantiles non-decreasing, inverse-logit
      probabilities strictly in (0, 1).
- [ ] Determinism: same input + seed gives identical CPU output; GPU within 1e-5.
- [ ] Load → forecast → unload cycles across all four sizes in sequence keep peak RAM under 8 GB
      and show memory released after `unload()`.
- [ ] Benchmarks saved in `benchmarks/` and summarised in `docs/STATUS.md`.
- [ ] Tests cover input validation, output structure, quantile handling, probability transforms,
      and a leakage test (values after `input_cutoff` are rejected).
- [ ] `timestral` is imported only in `src/mpe/models/timestral.py` (test enforces it).
- [ ] `docs/MODELS.md` answers every §3.2 item; `docs/STATUS.md` and `docs/KNOWN_LIMITATIONS.md` exist.
- [ ] No trading code.

### M1: Data ingestion and persistence

**Polymarket provider:** discover active markets; retrieve historical prices, YES/NO token ids,
current bid/ask and order book where available, volume, liquidity, resolution info; handle
pagination and rate limits (backoff, persisted request budget); store raw payloads where useful.
Market selection (20–50 markets): binary only, liquidity above a configurable threshold, enough
history, understandable resolution rules. Exclude multi-outcome, ambiguous and very illiquid
markets initially, but **store resolved and closed markets too** (survivorship), with
`selection_reason`.

**Stock provider:** yfinance first: historical daily OHLCV, daily updates, configurable watchlist
(`config/assets.yaml`), provider abstraction, error handling, missing-data detection, raw and
adjusted prices (corporate actions), a GBP/USD FX series stored as an asset. Add Stooq / Alpha
Vantage adapters only where useful.

**Provider interface:** `list_instruments()`, `fetch_history(instrument, start, end, interval)`,
`fetch_latest(instrument)`, `fetch_order_book(token_id)` (Polymarket), returning normalised
records with full provenance.

**Data quality:** timestamp normalisation to UTC, duplicate detection, missing-observation
detection (against the exchange calendar), outlier detection, stale-data detection, source
metadata, retrieval timestamps. Problems are written to `data_quality_events`. **Never silently
fabricate observations** (no forward-filling in storage).

CLI: `mpe ingest backfill`, `mpe ingest update`, `mpe data health`.

Acceptance:
- [ ] Both market categories ingested; the 10-instrument watchlist backfilled (from 2010 or listing);
      20–50 Polymarket binary markets stored with token ids and history, including ≥ 5 resolved.
- [ ] Repeated ingestion is idempotent (row counts unchanged on re-run).
- [ ] Injected API failures (timeouts, 429s, malformed JSON) leave the DB unchanged (transactional writes).
- [ ] Corrections create a new `version` row; old rows untouched.
- [ ] Validation tests pass using mocked providers / recorded fixtures; no live API in the default test run.
- [ ] `docs/DATA_SOURCES.md` documents each source's endpoints, limits, licensing and gaps.

### M2: Prediction laboratory

**Stocks** (SPY, QQQ, IWM, GLD, TLT, NVDA, MSFT, AAPL, AMZN, optional BTC-USD): forecast log
returns, price movements (reconstructed), volume where appropriate, volatility. Horizons 1, 5, 20
trading days.

**Prediction markets:** YES price movement, NO price movement, probability-price changes, trading
activity where appropriate; logit transform with careful 0/1 handling. Horizons 1, 6, 24 hours.
Market-price forecasting stays separate from event-resolution probability.

**Baselines:** persistence/random walk, moving average, momentum, simple trend extrapolation.

**Experiments** (YAML specs in `config/experiments/`, stored in `experiments`): four Timestral
sizes; univariate vs multivariate (e.g. SPY+QQQ+IWM(+VIX) returns; YES price with spread and
volume as past-only covariates); different input windows; different horizons; feature combinations.
Every experiment records model configuration, input cutoff, creation time, target time, forecast
values, actual outcomes (via `evaluations`) and runtime.

**Evaluation:** MAE, RMSE, directional accuracy, quantile/pinball loss, CRPS, interval coverage
(calibration), skill vs random walk with confidence intervals (block bootstrap) and a
Diebold–Mariano test. Chronological walk-forward only; never random splits. A **final untouched
test period** (last 20% of time, configurable) is excluded from all development and only scored by
`mpe evaluate --final`, which logs every invocation to `system_state`.

Acceptance:
- [ ] All operational models produce comparable forecasts on the same inputs, horizons and windows.
- [ ] Baselines operational.
- [ ] Walk-forward backtesting works; a planted-future-spike test proves no leakage.
- [ ] Re-running an experiment reproduces forecasts exactly (CPU) and writes new rows only.
- [ ] Forecast immutability enforced by DB triggers (tested).
- [ ] `mpe report models` generates a comparison by model × size × asset × horizon with sample
      sizes and uncertainty.

### M3: Signal generation and paper trading

Starting configuration (`config/risk.yaml` and `config/settings.yaml`):

```yaml
paper_trading:
  enabled: true
  real_trading_enabled: false     # must be false; startup aborts otherwise
portfolio:
  initial_balance: 1000
  currency: GBP
  maximum_position_value: 50
  maximum_total_exposure: 300
  maximum_open_positions: 10
  leverage: false
  short_selling: false
  compound_returns: true
risk:
  maximum_drawdown: 15            # percent; halts new positions
  stale_data_block: true
  require_valid_forecast: true
```

**Signals** (transparent, rule-based, thresholds in `config/strategies.yaml`): expected return,
forecast uncertainty (quantile width), the model's trailing out-of-sample accuracy vs baseline,
model agreement, transaction costs, liquidity, existing exposure. Every evaluation writes a
`signals` row, including skips, with each rule's outcome in `reasons_json`. No learned ensemble
weights yet.

**Execution simulator:** market orders; limit orders where practical; bid/ask spread; fees;
slippage; partial fills (Polymarket by walking the stored order-book snapshot); cash and position
accounting in `Decimal`; realised and unrealised P&L; exits; prediction-market resolution payouts
(1/0 per token; cancelled/invalid markets handled per their rules, separately). Stocks fill at the
next available session price plus spread and slippage, only in market hours. **Never fill at the
midpoint or last trade.**

**Safety:** no real execution path; no credentials; global kill switch; position, exposure and
drawdown limits; duplicate-order prevention (`idempotency_key`); stale-data protection;
invalid-price protection.

Acceptance:
- [ ] Simulated trades execute correctly; positions open, close and settle on resolution.
- [ ] Portfolio reconciles: cash + positions value = total equity at every snapshot, exactly in
      `Decimal`; positions are rebuildable from fills.
- [ ] Fees and slippage applied; buys use ask/book, sells use bid/book (tested).
- [ ] Risk limits reject a £60 order, an 11th position, exposure above £300, trades on stale data,
      trades after a 15% drawdown, and duplicate orders, each with a logged reason.
- [ ] Edge-case tests: partial fills, zero liquidity, price at 0 or 1, market cancelled, FX missing.
- [ ] Historical paper-trading replay over the non-holdout period produces a trade log and equity curve.

### M4: Dashboard and autonomous operation

**API:** FastAPI on `127.0.0.1` (§8.1). **Dashboard:** Streamlit, reading only the API. Screens:
Overview, Live predictions, Stock markets, Prediction markets, Open positions, Trade history,
Portfolio performance, **Model comparison** (by model, asset, market category, horizon,
volatility regime, strategy), Historical experiments, Data quality and system status. Overview
shows virtual balance, total equity, cash, open positions, realised and unrealised P&L, total
return, max drawdown, forecast count, simulated trade count, and a permanent PAPER MODE banner.

**Scheduler** (APScheduler, persistent job store in SQLite, all times configurable):
stock data after the daily close; Polymarket data every 15–60 min (within API limits);
Polymarket forecasts every 1–6 h; evaluation once targets are observable; portfolio snapshots
hourly. Skip forecasting when no new data has arrived since the last run. Graceful recovery after
restart (missed runs coalesced, `job_runs` uniqueness prevents duplicates). systemd units in
`deploy/`.

Acceptance:
- [ ] Dashboard works locally; model comparison shows real stored results.
- [ ] Scheduler runs unattended for 72 h; data and predictions persist across a restart mid-cycle.
- [ ] Errors logged and retried; jobs never create duplicate forecasts or trades.
- [ ] Paper trading is the only execution mode.
- [ ] Then start a **2–4 week live observation period** before trusting any apparent profitability.

#### 8.1 API contract (local only)

JSON, UTC ISO-8601 times, decimals serialised as strings, GBP unless stated. Pagination
`?limit=` (default 100, max 1000) and `?cursor=`. Errors: `{"error": {"code": "...", "message": "..."}}`.
There is no endpoint that can place a real order.

| Method and path | Purpose | Key params | Response |
|---|---|---|---|
| `GET /health` | Liveness | – | `{status, paper_mode: true, real_trading_enabled: false, db_ok, scheduler_running, kill_switch}` |
| `GET /assets` | Assets | `asset_type`, `active` | `[Asset]` |
| `GET /assets/{id}/observations` | History | `start`, `end`, `interval`, `as_of` | `[Observation]` |
| `GET /markets`, `GET /markets/{id}` | Prediction markets | `resolution_status`, `category` | `[Market]`, `MarketDetail` |
| `GET /models` | Registered models + capabilities + load state | – | `[ModelMetadata]` |
| `GET /forecasts` | Query forecasts | `asset_id`, `model`, `size`, `horizon`, `forecast_type`, `since` | `[Forecast]` |
| `GET /forecasts/{id}` | One forecast with its evaluation if available | – | `ForecastWithEvaluation` |
| `GET /signals` | Signals incl. skips, with reasons | `decision`, `strategy`, `since` | `[Signal]` |
| `GET /orders`, `GET /fills`, `GET /positions` | Paper-trading records | `status`, `since` | lists |
| `GET /portfolio` | Current state | – | `{cash, total_equity, exposure, open_positions, realised_pnl, unrealised_pnl, total_return, max_drawdown, trades}` |
| `GET /portfolio/history` | Equity curve | `start`, `end`, `mode` | `[PortfolioSnapshot]` |
| `GET /evaluations/comparison` | Model comparison | `group_by` (model, size, asset, category, horizon, regime, strategy), `metric`, `include_holdout=false` | `[EvaluationSummary]` |
| `GET /experiments`, `GET /experiments/{id}` | Experiments | – | lists / detail |
| `GET /data/health` | Freshness, gaps, quality events | – | `DataHealth` |
| `GET /jobs` | Scheduler runs | `job_name`, `status` | `[JobRun]` |
| `POST /admin/kill-switch` | Halt or resume new paper trades | `{enabled, reason}` | `{kill_switch}` |
| `POST /admin/jobs/{job_name}/run` | Run a job now | – | `{job_run_id}` |

Example `Forecast`:

```json
{
  "id": 1842, "model": "timestral", "size": "123M", "model_version": "a1b2c3d",
  "asset_id": 1, "symbol": "SPY", "forecast_type": "log_return",
  "input_cutoff_timestamp": "2026-11-02T21:30:00Z", "created_at": "2026-11-02T21:31:04Z",
  "horizon": 5, "horizon_unit": "trading_day", "target_timestamp": "2026-11-09T21:00:00Z",
  "forecast_values": {"median": 0.0021, "implied_price": {"q10": "573.90", "median": "581.40", "q90": "590.70"}},
  "quantiles": {"0.1": -0.012, "0.5": 0.0021, "0.9": 0.016},
  "experiment_id": 7, "runtime_ms": 41.2
}
```

### M5: Experimental improvements (only after M0–M4 work)

Adaptive model weighting, forecast ensembles, regime detection, cross-asset forecasting,
additional foundation models (Amazon Chronos, Salesforce Moirai, TiRex; Nixtla TimeGPT only after
checking cost and access), alternative features, prediction-market calibration, event-driven
forecasting, automated strategy discovery. **Each addition must answer a specific experimental
question**, not add a row to the dashboard. New models are new `ForecastModel` plugins. Strategy
discovery must keep the untouched evaluation set untouched and record every experiment tried.

---

## 9. Financial experiment integrity (critical)

Three separate things, reported separately:
- **Forecasting accuracy:** did the model predict the numerical movement?
- **Probability accuracy:** were estimated probabilities calibrated against actual outcomes?
- **Trading profitability:** did the strategy produce positive net returns after costs?

Stocks: use returns, account for corporate actions, use realistic trading calendars, avoid
look-ahead, include transaction costs.

Prediction markets: preserve snapshots as they were at prediction time; distinguish implied
probability from event probability (Timestral quantiles of a future price are **not** calibrated
event probabilities); track liquidity and spreads; respect resolution rules; handle ambiguous or
cancelled markets separately; do not treat unresolved events as failed predictions. Stale prices
and vanishing liquidity are data-quality and execution risks, never forecasting wins.

All experiments: preserve original predictions, record provenance and model versions,
chronological evaluation only, report sample sizes and uncertainty, account for survivorship and
selection bias, report the number of comparisons alongside any "best" result (multiple testing),
never silently discard losing trades or failed predictions. The system must be able to report
that a model has no demonstrated predictive advantage.

---

## 10. Logging and observability

Structured (JSON) logging with a `run_id` / `job_run_id` correlation field. Track ingestion
status, provider errors, forecast duration, model memory, scheduler status, prediction generation,
signal decisions, simulated orders, portfolio changes and evaluation results. Every signal explains
why a trade was or wasn't taken. No unexplained black-box decisions.

---

## 11. Testing requirements

Pytest, with mocked providers and recorded HTTP fixtures; the default suite needs no live API, no
GPU and no model weights (mark those tests `network`, `gpu`, `weights`).

Priorities: forecast input validation, model output validation, timestamp handling, ingestion,
duplicate prevention, persistence, walk-forward evaluation, future-data leakage, quantile handling,
probability transforms, portfolio accounting, position sizing, order execution, fees and slippage,
prediction-market resolution, risk limits, scheduler recovery.

Cross-cutting guard tests that must exist from the milestone they apply to and stay green:
- `test_timestral_isolated` (M0): `timestral` imported only in `models/timestral.py`.
- `test_no_real_trading_clients` (M0 onward): AST scan fails on imports of trading/wallet libraries
  (`py_clob_client`, `ccxt`, `alpaca`, `ib_insync`, `web3`, `eth_account`, …) and on any reference
  to authenticated order endpoints.
- `test_clock_injection` (M1): no `datetime.now()` / `time.time()` outside `clock.py`.
- `test_point_in_time` (M1/M2): planted future data never reaches features or forecasts.
- `test_immutable_tables` (M2/M3): UPDATE/DELETE on forecasts, signals, orders, fills raise.
- `test_orders_are_paper` (M3): `is_paper = 1` constraint; startup aborts if `real_trading_enabled`.
- `test_holdout_locked` (M2): development code paths refuse windows overlapping the final test period.

Do not suppress or skip failing tests to make a milestone look complete.

---

## 12. Documentation

Maintain `README.md` and `docs/ARCHITECTURE.md`, `docs/DATA_SOURCES.md`, `docs/MODELS.md`,
`docs/EXPERIMENTS.md`, `docs/PAPER_TRADING.md`, `docs/RISK_AND_SAFETY.md`, `docs/DEPLOYMENT.md`,
`docs/KNOWN_LIMITATIONS.md`, `docs/STATUS.md`.

`docs/STATUS.md` records: completed milestones, current milestone, working functionality,
outstanding issues, test results, performance benchmarks, next steps. Update it at the end of
every milestone and whenever a blocker is found.

---

## 13. Development workflow

1. Inspect the current repository before making changes; don't assume files don't exist.
2. Verify upstream interfaces before implementing integrations.
3. Make small, coherent changes; keep each milestone independently usable.
4. Run relevant tests after every meaningful change.
5. Do not suppress failing tests.
6. Document actual limitations rather than pretending they are solved.
7. Avoid premature abstractions and unnecessary dependencies.
8. Do not start a later milestone while the current one has unresolved critical blockers.
9. Use a branch and pull request per milestone (`milestone/m0-timestral` etc.) with a clear
   implementation report in the PR description.

---

## 14. Initial task: M0 only

Do not implement M1–M5 yet. In order:

1. Inspect the repository and available environment.
2. Research the actual Timestral upstream implementation (§3.2).
3. Check GTX 1060 compatibility.
4. Create the minimal Python project.
5. Implement the forecasting abstraction.
6. Get one Timestral model running (5M, CPU).
7. Expand to the other model sizes.
8. Benchmark CPU and GPU.
9. Write tests.
10. Document the results (`docs/MODELS.md`, `docs/STATUS.md`, `docs/KNOWN_LIMITATIONS.md`).

No dashboard, no paper-trading simulator, no paid data services in M0. M0 proves that the central
forecasting technology works on the intended hardware.

---

## 15. Final instruction

Think of this project as an autonomous quantitative research laboratory, not a trading advice
application. It continuously collects observations, generates forecasts, records predictions,
evaluates results and runs controlled paper-trading experiments, and it must make it possible to
determine whether Timestral genuinely provides predictive value beyond simple statistical
baselines.

Build the smallest working version first. Measure everything. Expand only when the evidence
justifies it.
