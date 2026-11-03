# TimeBalance

Market Prediction Engine: a local-first, autonomous paper-trading research lab that tests
Mistral's Timestral time-series models against simple baselines on stocks and Polymarket.

Paper trading only. See `docs/IMPLEMENTATION_PROMPT.md` for the implementation brief.

## Quick start (M0)

```bash
uv sync                                        # Python 3.12, torch 2.14.1+cu126 (GTX 1060 capable)
uv run pytest                                  # offline unit tests
uv run python scripts/download_models.py       # all four Timestral sizes into data/models/
uv run pytest -m "weights or gpu"              # real-weight and GPU checks
uv run python scripts/m0_demo.py               # sample forecasts, every model
uv run python scripts/m0_benchmark.py          # CPU vs GPU benchmark -> benchmarks/
```

Status: `docs/STATUS.md`. Model facts: `docs/MODELS.md`. Limitations: `docs/KNOWN_LIMITATIONS.md`.
