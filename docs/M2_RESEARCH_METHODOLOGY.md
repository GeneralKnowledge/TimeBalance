# M2 research methodology

_Applies to the `mpe research` laboratory (`src/mpe/research/`), configuration version `m2.1`._

The laboratory asks whether Timestral forecasts stored history better than simple baselines. It is
built to be able to say "no": every comparison is paired, out of sample, and reported with its
sample size and uncertainty. Nothing here is a trading signal.

## 1. Experiments

An experiment is one `ExperimentConfig` (`src/mpe/research/config.py`). Every field that can
change a forecast or a score is written into the saved JSON, including model constructor
parameters, quantile levels, the replay mode, the availability rule text, delays, the context
length, the seed and the requested device. Nothing is taken from a default at run time.

The experiment id is `<domain>-<first 12 hex of sha256(canonical config JSON)>`, computed over
every field except `name` and `notes`. The same configuration therefore always has the same id
(creating it twice is refused), and any change produces a different id, so results from different
configurations cannot be merged. Model versions (Timestral Hugging Face revision, baseline code
version) and the git commit are recorded when the experiment is created and on every model run. A
model whose version changes in the middle of an experiment is refused (`VersionChanged`).

```bash
uv run mpe research assets --domain stocks
uv run mpe research create --domain stocks --mode reconstructed --start 2012-03-01 --end 2026-09-29 \
    --stride 1 --targets-as-of 2026-11-03T00:00:00Z
uv run mpe research run <id>                  # Ctrl-C at any time; the same command resumes
uv run mpe research run <id> --max-forecasts 5000   # or work in resumable batches
uv run mpe research show <id> [--section comparisons|calibration|assets|exclusions|runs]
uv run mpe research report <id>               # reports/experiments/<id>/report-<hash>/
uv run mpe research export <id> --format csv  # raw forecasts, targets, origins and metrics
```

To reproduce an experiment elsewhere, save its configuration (`show <id> --section config`) and
pass it back with `create --config FILE` against the same market data. Preparation stores a hash of
every model input; if the data seen at any cutoff differs on resume, the run stops with
`DataChanged` instead of mixing inputs.

## 2. Walk-forward design

There is no training, tuning or random split. Each model sees, at each origin, only the past.

- **Origin** `t_o`: a grid point. For stocks the grid is the XNYS session closes from
  `exchange_calendars` (holidays and early closes included). For Polymarket it is the UTC hour of
  the hourly price sample. Origins are every `origin_stride` sessions from the first session on or
  after `origin_start` (stocks), or every UTC hour whose index since the epoch is divisible by the
  stride (Polymarket). Origins outside an asset's stored span, and Polymarket origins less than an
  hour before the market's scheduled close, are not generated and are counted.
- **Cutoff** `= t_o + cutoff_delay_seconds`. Stocks: 1,800 s, the availability delay of a daily bar
  (session close + 30 min). Polymarket: 300 s; the sample for hour `H` is taken in the first
  minute of the hour and is available 60 s later, so a cutoff of `H + 5 min` normally includes it.
- **Context**: the last `context_length` target values on the grid up to `t_o`, read at the cutoff
  through the replay accessor. The cutoff is passed to `ForecastInput.input_cutoff`, so
  `validate_input` rejects any context point after it; the research code also asserts that no row
  returned by the accessor is later than the cutoff.
- **Targets**: one forecast path of `max(horizons)` steps per origin; the step-`h` value is scored
  for each configured horizon `h`. Future timestamps are the next grid points after `t_o` (actual
  sessions, so a Friday origin's 1-session target is Monday's close, or Tuesday's after a holiday).
- **Realised values** are read once per asset at `targets_as_of`, through the same accessor and the
  same replay mode. A case is scored only if its target exists in that read.

Each model gets exactly the same context, future timestamps, quantile levels and seed.

## 3. Replay modes

`knowledge_mode` is required and never substituted.

| mode | accessor | meaning |
|---|---|---|
| `strict_point_in_time` | `repositories.get_history` | what the system actually had retrieved by each cutoff |
| `reconstructed_history` | `replay.get_reconstructed_history` | what it could have known, from backfilled data, under the documented availability rules |

`research.data.read_history` is the only function in the research package that reads observations.
It calls exactly one accessor and checks the frame's `knowledge_mode` attribute against the
experiment, so strict and reconstructed rows can never be mixed. A guard test checks that no other
research code refers to the observations table (the asset listing is descriptive only).
`extra_latency_seconds` (reconstructed only) delays every row further, for pessimistic tests.

Every origin row stores provenance: counts of `captured` and `reconstructed` rows, the highest
version used, sources, and any off-calendar, missing or invalid rows. Every realised target stores
its `available_at`, `version` and `knowledge`. Reports carry a banner: **reconstructed research is
not what the system genuinely knew at the time.** All data in the current database was retrieved on
2026-11-03, so strict replay of any earlier cutoff is empty; that is the correct answer, not a bug.

## 4. Targets

**Stocks:** daily log returns of `close` (`STOCK_PRICE_FIELD`; `adj_close` is not used). The
return at session `s` is `ln(close_s / close_prev)`, where `prev` must be the previous XNYS
session. It is computed with `stock_log_returns` over consecutive present bars and kept only when
the previous present bar is the previous session; a return is never computed across a gap.
Rows whose timestamp is not a session close (^VIX has two bars on 2026 market holidays) are left
out and counted. Horizons: 1, 5 and 20 sessions. The step-`h` target is the single-day return `h`
sessions ahead, not the cumulative `h`-day return (per-step quantiles do not add up; see
`KNOWN_LIMITATIONS.md`).

**Polymarket:** the YES token's hourly price sample, transformed with `logit` (clipped to
`[1e-4, 1 - 1e-4]`). The YES asset is found through `assets.outcome_side = 'YES'` and checked
against `markets.yes_token_id`; the NO token is never used as a YES probability. Forecasts are
mapped back with `inv_logit`, so every reported probability is strictly inside (0, 1). Horizons: 1,
6 and 24 hours. With `respect_closing_time`, targets after the market's scheduled close
(`markets.closing_time`, known in advance) are not scored.

## 5. Missing data and exclusions

Nothing is forward-filled for evaluation. The baselines' own context handling (`_ffill` inside the
model) does not change the stored context or any target.

| situation | rule | recorded as |
|---|---|---|
| a context point missing or non-finite / non-positive price | NaN in the context | provenance counts |
| the origin's own observation not available at the cutoff | origin excluded | `origin_observation_missing` |
| fewer than `min_context_observations` valid points | origin excluded | `insufficient_context` |
| more than `max_missing_context_fraction` missing inside the observed span | origin excluded | `too_many_missing_context` |
| duplicate timestamps in a history read | origin excluded | `duplicate_timestamps` |
| target bar or its previous session missing | case not scored | `target_missing` |
| target not knowable by `targets_as_of` | case not scored | `target_not_yet_available` |
| target after the market's scheduled close | case not scored | `after_market_close` |
| model error or output failing `validate_output` | forecast stored as failed | `research_forecasts.error` |

A forecast fails if it raises, if `validate_output` fails (shape, finite values, monotone
quantiles), if the quantile levels differ from the requested ones, or if its timestamps differ from
the requested target timestamps. Failures are never retried silently and never dropped: they appear
in the report, and the affected origin leaves the common sample (below) for every model.

## 6. Scoring

All models are scored on the **common sample**: the (asset, origin, horizon) cases where every
model produced a valid forecast and the realised target exists. Definitions
(`src/mpe/research/metrics.py`):

- error = median forecast − actual (positive mean signed error = over-forecasting)
- MAE, RMSE, mean signed error
- directional accuracy: share of cases where the sign of the predicted change equals the sign of
  the actual change, among cases where neither is exactly zero; the zero counts are reported. For
  returns the change is the return itself; for Polymarket it is the logit change from the origin.
  Directional accuracy is not profitability.
- pinball loss per level, `max(τ(y − q), (τ − 1)(y − q))`, and its mean over the 21 levels
- **CRPS_q**: `2 ∫ ρ_τ(y − q_τ) dτ` over `[0.01, 0.99]`, trapezoidal rule over the 21 (uneven)
  levels. No extrapolation outside the native level range, so the tails beyond 1% and 99% are
  omitted and CRPS_q is smaller than the full CRPS. It is a proper comparison between models on
  the same level set, which every experiment enforces. (The mean pinball loss is reported
  separately and is not called CRPS.)
- coverage of the central 50/80/90/98% intervals (closed intervals between the 0.25/0.75,
  0.1/0.9, 0.05/0.95 and 0.01/0.99 quantiles) and their average width
- quantile calibration error: mean over levels of |share of outcomes ≤ q_τ − τ|
- Polymarket also reports MAE and RMSE in probability space, and pinball and CRPS_q of the
  inverse-logit quantiles (inverse logit is monotone, so quantiles map to quantiles).

The point forecast is the 0.5 quantile for every model. For the baselines that is the point
forecast plus the median of their own in-sample errors (M0 design), so `zero` is not literally 0.

## 7. Comparisons and uncertainty

The reference baseline is `zero` for stock returns (zero log return = random-walk price) and
`persistence` for Polymarket prices (last price; `zero` would mean 50%). Relative improvement is
`1 − metric / metric(reference)`; positive is better.

Paired comparisons (`analysis.paired`) take each Timestral model against the reference and against
the best baseline for that horizon and loss (absolute error and CRPS_q). The best baseline is
chosen on the same evaluation sample, which favours the baseline. For each case the loss difference
`d = loss(model) − loss(comparator)` is computed; the estimate is the pooled mean of `d`. Its 95%
interval comes from a moving-block bootstrap over origin dates: all assets at a date stay together
(cross-sectional correlation), and blocks of consecutive dates of length
`max(ceil(h / stride), ceil(n_dates^(1/3)))` keep the overlap of multi-step targets and short-range
dependence (2,000 resamples, seeded). An ordinary i.i.d. bootstrap is not used.

Conclusions:

- **better** / **worse**: the interval excludes zero.
- **no demonstrated difference**: it does not. The model has not shown an advantage; this is not
  proof that the two are equal.
- **insufficient data**: fewer than `min_paired_dates` (30) origin dates, or fewer than 10 blocks.

The report states how many comparisons were made; with 5% intervals, about one in twenty can
exclude zero by chance.

## 8. Aggregation

- **Pooled** metrics give every scored case equal weight.
- **Macro** metrics are the unweighted mean of per-asset metrics, so an asset with many origins
  (a long-lived market) does not dominate. Both are in the leaderboard and they are kept apart.
- Per-asset, per-horizon, per-model and over-time (calendar year for stocks, month for Polymarket)
  tables, plus the overall leaderboard.

## 9. Calibration

For each model and horizon: nominal versus empirical coverage of the central intervals, average
width, and the share of outcomes below each quantile (plotted against the diagonal in
`calibration_h<h>.svg`). With overlapping origins the effective sample is much smaller than `n`, so
small deviations are not evidence of miscalibration. A narrow interval is good only if its coverage
holds.

## 10. Polymarket: prices versus outcomes

The primary task is forecasting the market price. A secondary analysis uses resolved markets with
a YES/NO outcome: only origins whose cutoff is before both the scheduled close and the recorded
resolution time count. It reports Brier scores of (a) the market price at the origin and (b) each
model's forecast price, each read as a probability of YES. A price forecast is not an
event-probability model, `resolutions.resolved_at` is the API's last update (it can be later than
the moment the outcome was known), and origins of one market are strongly dependent; with the
current 12 resolved markets these numbers support no calibration claim and are reported separately
from the price metrics.

**Selection and survivorship.** The universe is every market in the selected panel, open and
resolved, not only markets active today. The panel itself was chosen by lifetime volume from the
markets scanned in M1 (`markets.selection_reason` is stored for all 1,200 scanned markets; 851 were
excluded as legs of multi-outcome events), and resolved markets come only from the last 365 days of
closes. Results describe high-volume binary markets in 2025–2026, dominated by geopolitics and
crypto-price thresholds, not prediction markets in general.

## 11. Statistical limitations

- Overlapping horizons (a 20-session target with stride 1) make neighbouring cases strongly
  dependent; the block bootstrap accounts for this only approximately.
- Asset returns are cross-correlated (SPY, QQQ, IWM). Ten stock series are not ten independent
  samples.
- Every result is conditional on the period studied. The over-time table shows whether an
  advantage holds across years or comes from one regime.
- No multiple-testing correction is applied; the number of comparisons is reported instead.
- There is no held-out final test period yet: nothing is tuned, so there is nothing to overfit,
  but any future model selection based on these reports must be validated on later data.

## 12. Storage

Research results live in `data/research.sqlite3` (`research_database_path`), separate from the
market-data database, which research commands open read-only (`mode=ro`, `query_only`). The
operational `forecasts`/`evaluations` tables are untouched and stay reserved for live forecasting.
`research_origins`, `research_targets` and `research_forecasts` are immutable (SQLite triggers
refuse UPDATE and DELETE); `research_forecasts` has one row per (experiment, model, asset, origin),
so a forecast cannot be duplicated. Medians and quantiles are stored at the configured horizons as
little-endian float64 blobs (`export` writes them as CSV/JSON).

Reports are written to `reports/experiments/<id>/report-<hash of results>/` and never overwritten:
the same results map to the same directory, new results get a new one.

## 13. Compute

Models are created from the configuration and loaded through `ModelManager(max_resident=1)`, one
at a time, and unloaded before the next (also on interruption). Each model run records the device,
total and per-forecast inference time, wall time, peak process RSS and peak CUDA memory. Timestral
receives one series per call: the upstream batch API is not used (see `KNOWN_LIMITATIONS.md`).
