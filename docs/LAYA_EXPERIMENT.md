# Laya decision-model experiment (M3-L)

_Started 2026-11-03. Research and paper analysis only: nothing here places orders, holds keys or
connects to a broker._

## Question

Does Laya give a decision signal on Polymarket that the market price, simple quantitative
baselines and Timestral do not already provide?

## What Laya is (verified 2026-11-03)

Checked against the Hugging Face repos, the GitHub README and the source of `laya` 0.4.22 from PyPI.

| | |
|---|---|
| Project | github.com/NandhaKishorM/laya, Apache-2.0. Canonical weights `convaiinnovations/laya`; `Infin8-AI/laya` is a duplicate of it |
| Model | ModernBERT-large encoder + a small decision head, 421M parameters, fp16 safetensors (~843 MB per checkpoint) |
| Checkpoints | repo root (English, 512 tokens), `multilingual` (mmBERT-base, 322M), `typed-decisions` (1,024 tokens, fine-tuned on four business workflows: invoices, security incidents, customer service, agent traces) |
| Inference | Not generative. One forward pass scores predefined options. `laya.load(repo, subfolder=...)`, then `agent.predict_batch(states, questions)` |
| Question types | `choice` (labels with descriptions), `score` (ordinal rubric), `noul` (P(true)) |
| Output | Per question: `probabilities`, `confidence`, `answer_confidence`, `action.act_probability` |
| Quantisation | None documented. Options are fp16/bf16 autocast, `torch.compile`, ONNX, a TileLang path |
| Requirements | Python ≥ 3.10, torch ≥ 2.0, transformers ≥ 4.48. It fits the existing environment without changing torch |

Its own model card warns that:

- the base checkpoints are near chance on typed decisions without fine-tuning;
- probabilities ship over-confident (mean ECE 0.466 before refitting temperatures);
- `act_probability` carries no usable signal;
- `noul` can follow its option labels instead of the input.

**Prior expectation.** Laya has no knowledge of events after pretraining and cannot look anything
up. All it can use is the text and numbers in the snapshot, and the price already sums those up. We
expect it not to beat the market price. The experiment is set up so that this can be shown cheaply.

## Architecture decisions

1. **A separate interface.** `mpe.decisions.base.DecisionModel` (load / unload / metadata /
   `decide_batch`) and its dataclasses are new. `mpe.models.base.ForecastModel` and Timestral are
   untouched, and nothing in the forecasting pipeline imports `mpe.decisions`.
2. **Provider-independent questions.** `DecisionQuestion` has a kind (`binary`, `choice`,
   `ordinal`), a prompt, candidate answers with descriptions, and an optional abstention threshold.
   The questions are configured in `config/decision_tasks.yaml`, and their content hash is stored
   with every run.
3. **Laya adapter.** `mpe.decisions.laya_model.LayaDecisionModel` maps binary questions to
   two-option `choice` questions by default, following the card's workaround for `noul`; `--binary-as noul` tests the other mapping. It maps ordinal questions to
   `score`. It keeps the raw output and records errors per request instead of crashing.
   `laya` is an optional extra (`.[laya]`).
4. **Separate, append-only store.** `data/decisions.sqlite3` holds the resolved-market sample,
   hourly YES history, snapshots, runs, raw and normalised outputs, and evaluations. It never
   writes to `data/mpe.sqlite3` or `data/research.sqlite3`. A rerun is a new run id. Reports go
   to `reports/decisions/<run>/<eval>/` and refuse to overwrite.
5. **Data source.** The existing `PolymarketProvider` (Gamma discovery, CLOB hourly
   `prices-history`) fetches resolved binary markets. The live panel has only about 12 resolved
   markets, too few to score a resolution probability.
6. **Point-in-time snapshots.** Snapshots are taken 168, 48, 24 and 6 hours before each market's
   *scheduled* end, and only while the market was still open. A snapshot uses only prices with
   `available_at <= decision_ts`. Gamma's post-resolution volume and liquidity, historical
   spreads and news are listed as `unavailable` rather than filled in. **All results are
   reconstructed**, because the history was fetched after resolution.
7. **Walk-forward evaluation.** Recalibration (Laya → P(YES)), the market-plus-Laya combination
   and the base rate are refitted for each decision time. Each fit uses only markets that
   resolved before that time. Confidence intervals resample whole markets.

## Baselines

- `market`: the last YES price at the decision time.
- `market_recal`: walk-forward logistic recalibration of the price, to correct favourite–longshot
  bias.
- `base_rate`: the walk-forward share of markets that resolved YES.
- Direction: `persistence` (always unchanged) and `momentum` (the sign of the last 24 h move).
- Timestral: M2 found Timestral worse than the last price at 1 h and no better on the median at
  24 h. It forecasts prices, not resolution, so it isn't scored here; see
  `reports/experiments/polymarket-cd414105d4c8`.

## Running it

```bash
# laptop, inside ~/TimeBalance. This adds laya and leaves torch/timestral as they are.
uv sync --extra laya
uv run pytest -q                                    # existing suite + tests/unit/test_decisions.py

uv run mpe decide fetch --end-min 2026-05-01 --end-max 2026-10-31 --max-markets 300
uv run mpe decide snapshots --leads 168,48,24,6
uv run mpe decide run --checkpoint typed-decisions --device cuda      # or --device cpu
uv run mpe decide evaluate <RUN_ID>
uv run mpe decide evaluate <RUN_ID> --fee-rate 0.02                   # fee sensitivity
uv run mpe decide runs
```

`run` records the load time, peak RSS, peak VRAM, latency per snapshot (mean and p95), decisions
per second and the failure rate. It unloads the model and clears the CUDA cache at the end.

## Questions asked (config/decision_tasks.yaml, `pm-questions/v1`)

A. `resolves_yes`: P(YES), compared with the market price.
B. `direction_6h`, `direction_24h`: rise, fall or unchanged (within 1 point).
C. `regime`: trending up, trending down, range-bound, high volatility, low liquidity or unstable.
D. `opportunity`: strong NO … strong YES, scored as a paper signal only.
E. `enough_information`: a P(enough) below 0.5 counts as abstaining. Metrics are also reported
   on answered points only.

The model's confidence is recorded as `laya.answer_confidence`. It is never treated as
calibration; calibration is measured (ECE and reliability) on outcomes.

## Stop rule

If raw and recalibrated Laya both fail to beat `market` on Brier score (95% interval excluding
zero in Laya's favour), and the disagreement correlation is not reliably positive, we recommend
stopping. In that case the regime, opportunity and multi-checkpoint follow-ups are not built.
