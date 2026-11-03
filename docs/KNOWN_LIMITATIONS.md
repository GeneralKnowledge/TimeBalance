# Known limitations

_As of M0 (2026-11-03)._

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
