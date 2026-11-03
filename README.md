# TimeBalance

Market Prediction Engine: a local-first, autonomous paper-trading research lab that tests
Mistral's Timestral time-series models against simple baselines on stocks and Polymarket.

Paper trading only. See `docs/IMPLEMENTATION_PROMPT.md` for the implementation brief.

## Models (M0)

```bash
uv sync                                        # Python 3.12, torch 2.14.1+cu126 (GTX 1060 capable)
uv run pytest                                  # offline unit tests
uv run python scripts/download_models.py       # all four Timestral sizes into data/models/
uv run pytest -m "weights or gpu"              # real-weight and GPU checks
uv run python scripts/m0_demo.py               # sample forecasts, every model
uv run python scripts/m0_benchmark.py          # CPU vs GPU benchmark -> benchmarks/
```

## Data (M1)

```bash
uv run mpe db init                             # create / migrate data/mpe.sqlite3
uv run mpe -v ingest backfill                  # watchlist from 2010 + Polymarket panel (~10 min)
uv run mpe -v ingest update                    # incremental; safe to re-run
uv run mpe data health                         # freshness, gaps, quality events, recent jobs
deploy/install_user_timers.sh --enable         # systemd user timers for automatic updates
```

Reading history: `get_history` is strict point-in-time replay (what the system actually knew);
`mpe.storage.replay.get_reconstructed_history` is labelled backfill research. See
"Reading history" in `docs/DATA_SOURCES.md`.

Status: `docs/STATUS.md`. Data sources: `docs/DATA_SOURCES.md`. Model facts: `docs/MODELS.md`. Limitations: `docs/KNOWN_LIMITATIONS.md`.
