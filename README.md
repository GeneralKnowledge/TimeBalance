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

## Research (M2)

```bash
uv run mpe research assets --domain stocks             # coverage and data-quality warnings
uv run mpe research create --domain stocks --mode reconstructed --stride 1   # prints the experiment id
uv run mpe research run <id>                           # all models, one at a time; Ctrl-C and re-run to resume
uv run mpe research show <id> --section comparisons    # paired comparisons with block-bootstrap intervals
uv run mpe research report <id>                        # reports/experiments/<id>/report-<hash>/
uv run mpe research export <id> --format csv           # raw forecasts, targets and metrics
```

Walk-forward evaluation of the four Timestral sizes against five baselines on daily stock returns
(`close`, XNYS sessions) and hourly Polymarket YES prices (logit). `--mode` is required: `strict`
(what the system actually knew) or `reconstructed` (backfilled data under documented availability
rules, labelled as such everywhere). The market database is opened read-only; results go to
`data/research.sqlite3`. Method: `docs/M2_RESEARCH_METHODOLOGY.md`.

Status: `docs/STATUS.md`. Data sources: `docs/DATA_SOURCES.md`. Model facts: `docs/MODELS.md`. Limitations: `docs/KNOWN_LIMITATIONS.md`.
