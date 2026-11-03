# Models

## Timestral

Upstream code: https://github.com/mistralai/timestral at commit
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff` (2026-10-15), pinned in `pyproject.toml`. Code is
Apache-2.0; the weights are under Mistral's Modified MIT licence (each `data/models/<name>/LICENSE`
is kept beside its weights). File/line references below are to that commit.

Only `src/mpe/models/timestral.py` imports `timestral` (enforced by `tests/unit/test_guards.py`).

### Checkpoints (Hub revisions recorded in `data/models/manifest.json`)

| Size | Repo | Revision | Weights | Layers | d_model | heads | MLP hidden |
|---|---|---|---|---|---|---|---|
| 5M | `mistralai/Timestral-5M` | `bdd20cfc15a3` | 20.8 MB | 8 | 192 | 3 | 512 |
| 28M | `mistralai/Timestral-28M` | `49b26409ac87` | 111.3 MB | 12 | 384 | 6 | 1024 |
| 123M | `mistralai/Timestral-123M` | `5a147287addd` | 490.4 MB | 20 | 640 | 10 | 1712 |
| 209M | `mistralai/Timestral-209M` | `9874d252ab0a` | 837.3 MB | 24 | 768 | 12 | 2048 |

From each `config.json`: every size uses `patch_size` 32, `block_size` 32 patches (so one decode
pass covers 1,024 steps), `context_length` 32,768, `covariate_enabled: true`, and a layer schedule
of repeating `[time, time, time, time_variate]` groups (2, 3, 5 and 6 groups respectively).
Every fourth layer adds attention across variates; the rest attend along time only. All sizes
satisfy `supports_known_covariates` (`src/timestral/config.py:98`).

### Answers to the brief's §3.2 questions

**Call signature** (`src/timestral/forecaster.py:161-172`):

```python
TimestralForecaster.forecast(
    context,                       # (B, V, T), (B, T) or (T,); NaN = missing
    prediction_length,             # int >= 1
    observation_mask=None,         # bool, like context; False = also missing
    past_covariates=None,          # (B, C_past, T)
    known_covariates=None,         # (B, C_known, T + prediction_length)
    categorical_past_covariates=None,   # (B, C, T) numeric codes, NaN = missing
    categorical_known_covariates=None,  # (B, C, T + prediction_length)
    symmetric_averaging=True,
    clip_nonnegative=True,
) -> Forecast   # .quantiles: torch.Tensor (B, V, H, Q)
```

- **Multivariate targets:** the middle axis of `context` is the variate axis. All V variates of
  one series are forecast jointly (variate attention within the series); output is
  `(B, V, H, Q)`. `(B, T)` means B univariate series. (`forecaster.py:233-244`)
- **Past-only covariates:** `past_covariates`, `(B, C_past, T)`, must cover exactly the context
  (`forecaster.py:352`). They are conditioning rows; they never read the targets and are not
  forecast. During multi-block decoding they get a blank (unobserved) future
  (`forecaster.py:446-447`).
- **Known-future covariates:** `known_covariates`, `(B, C_known, T + H)`; the last H columns are
  the future values (`forecaster.py:363`). Rows whose values are all 0/1 are treated as
  indicators (no asinh squash). Raises if the checkpoint cannot route them (`forecaster.py:217`).
- **Categorical covariates:** numeric codes. For a univariate target they are target-encoded per
  series (`covariate_encoding.py`); for multivariate targets the raw codes are used.
- **Quantile levels:** fixed by the checkpoint, 21 levels
  `0.01, 0.05, 0.10, 0.15, …, 0.90, 0.95, 0.99` (0.05 steps, confirmed in every `config.json`).
  `Forecast.quantile(q)` only accepts those exact levels and raises `ValueError` otherwise
  (`forecaster.py:53-57`). Our adapter accepts any levels within [0.01, 0.99] by linear
  interpolation between trained levels (flagged in `extra["quantiles_interpolated"]`) and refuses
  levels outside that range rather than extrapolate. Quantiles are monotone by construction
  (`model.py:57`, monotone quantile head) and sorted.
- **Batching:** yes. B is the batch axis: many series per call, each with its own variates.
  Series in a batch must share T (pad with NaN on the left). Our adapter currently sends B = 1.
- **Frequency argument:** none. The model sees only the value sequence; sampling interval is
  implicit. Nothing in the source takes a frequency or timestamps.
- **Determinism:** inference runs under `torch.inference_mode()` with `dropout_p=0.0`
  (`layers.py:138`); there is no sampling anywhere. Quantiles come from a deterministic head.
  Measured: repeated calls are bit-identical on CPU and on the GTX 1060 (max diff 0 across all
  72 benchmark cells). GPU vs CPU differ by at most 1.2e-6 (ctx 2048, h 20, all sizes).
  Seeding is not needed, but the adapter still calls `torch.manual_seed(seed)`.
- **Symmetric averaging** (default on, `forecaster.py:220-227`): forecasts `context` and
  `-context` and averages the reflected result, so each forecast is two forward passes. We keep it
  on (it is part of the evaluated forecaster).
- **Non-negative clipping** (upstream default on): clamps forecasts at 0 for any series whose
  observed context is entirely non-negative. **Our adapter defaults it off**: a positive price
  or YES-price series would be silently clipped, and log returns / logits are signed anyway.
- **Context cap:** the most recent 32,768 steps are kept, counting the target and covariate rows
  together (`forecaster.py:373-375`). Our interface truncates first and records it in
  `input_window`.
- **Long horizons:** past one decode block (1,024 steps) the forecaster continues block by block,
  feeding back each block's median (`forecaster.py:420-456`). Our adapter caps `max_horizon` at
  1,024 so every forecast is a single non-recursive pass.
- **Loading and caching:** `from_pretrained` accepts a Hub id or a local directory
  (`loading.py:19-48`). With a Hub id it downloads `config.json` and `model.safetensors` to the
  Hugging Face cache once. We download explicitly with `scripts/download_models.py` into
  `data/models/` and load from there, so runtime never touches the network.
- **Unloading:** dropping the forecaster, `gc.collect()` and `torch.cuda.empty_cache()` return
  allocated VRAM to zero, except for an 8 MiB cuBLAS workspace that PyTorch keeps in its caching
  allocator. The adapter clears it with `torch._C._cuda_clearCublasWorkspaces()` (private API;
  guarded with `getattr`). After that, `torch.cuda.memory_allocated()` is 0 (tested in
  `tests/integration/test_timestral_weights.py`). Host RAM also returns to its pre-load level once
  the adapter calls glibc `malloc_trim(0)` on unload (measured: 549 MB after each of the four sizes
  on CPU). The CUDA runtime, cuBLAS and kernel images add about 780 MB of host RSS on the first GPU
  forecast and stay for the process lifetime (1,301 MB after every unload on GPU); that is
  PyTorch/CUDA, not the model.
- **dtype:** `load_model` takes a `dtype` (default float32; "inference was validated in float32",
  `loading.py:57-62`), but `TimestralForecaster.from_pretrained` does not expose it. We run fp32.
  See the fp16 note in `docs/STATUS.md`.

### GTX 1060 (Pascal, compute capability 6.1)

- Default PyPI torch wheels (CUDA 12.8+) no longer ship Pascal kernels.
- We pin torch from the PyTorch **CUDA 12.6** index (`pyproject.toml`, `[tool.uv.sources]`).
  Resolved: `torch 2.14.1+cu126`. `torch.cuda.get_arch_list()` =
  `['sm_50', 'sm_60', 'sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90']`.
- `sm_61` is not listed, but `sm_60` cubins are binary-compatible with `sm_61`, and they run:
  every test and benchmark ran on the 1060. `mpe.models.timestral.cuda_usable()` checks for a
  same-major, lower-or-equal-minor cubin (or a PTX entry), not an exact match.
- Driver 550.163.01 reports CUDA 12.4; the cu126 wheel bundles its own CUDA 12.6 runtime and works
  through CUDA minor-version compatibility.
- **Risk:** a future cu126 release may drop `sm_60`, and newer torch versions may stop publishing
  cu126 wheels. `uv.lock` pins the exact wheel; check `get_arch_list()` before upgrading torch.

## Baselines

`src/mpe/models/baselines.py`, applied independently per series, no covariates (requests with
covariates raise `UnsupportedRequest`):

| name | point forecast |
|---|---|
| `persistence` | last observed value (random walk) |
| `moving_average` | mean of the last 20 values |
| `momentum` | last value + k × mean change over the last 20 steps |
| `linear_trend` | OLS line over the last 60 values, extrapolated |

Quantiles: each baseline is re-run at up to 250 past origins inside the context; its k-step-ahead
errors are added to the point forecast at the requested levels (default the same 21 levels as
Timestral). With fewer than 20 realised k-step errors, the 1-step errors scaled by √k are used.
The reported median is the 0.5 quantile of that error-adjusted distribution, so it includes the
method's in-sample median bias (for `persistence` it is not exactly the last value).

Baselines operate on whatever target series they are given. On log returns, `persistence` means
"tomorrow's return equals today's", which is not the price random walk; the price random walk on
returns is a zero forecast. M2 should add a `zero` / `historical_mean` baseline for return targets.
