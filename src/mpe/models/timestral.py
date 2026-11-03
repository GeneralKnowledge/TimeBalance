"""Timestral adapter. The only module in the project allowed to import ``timestral``.

Upstream: https://github.com/mistralai/timestral (pinned commit in pyproject.toml).
API facts used here are documented with file/line references in docs/MODELS.md.
"""

from __future__ import annotations

import ctypes
import gc
import json
import time
from pathlib import Path

import numpy as np
import torch

from mpe.models.base import (
    ForecastInput,
    ForecastOutput,
    ModelMetadata,
    ModelNotLoaded,
    UnsupportedRequest,
    _to_ns,
    interpolate_quantiles,
    resolve_levels,
    truncate_context,
    validate_input,
)

SIZES: dict[str, str] = {
    "5M": "mistralai/Timestral-5M",
    "28M": "mistralai/Timestral-28M",
    "123M": "mistralai/Timestral-123M",
    "209M": "mistralai/Timestral-209M",
}
MAX_CONTEXT = 32_768  # trained context length (config.context_length)
# Longer horizons work upstream (block-autoregressive on fed-back medians), but we cap at one
# decode block so every forecast is a single, non-recursive pass.
MAX_HORIZON = 1_024
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"


def _trim_heap() -> None:
    """Ask glibc to return freed heap pages to the OS, so RSS drops after unload (Linux only)."""
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def cuda_usable() -> tuple[bool, str]:
    """Whether this torch build can run kernels on GPU 0, with a reason."""
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() is False"
    major, minor = torch.cuda.get_device_capability(0)
    arch = f"sm_{major}{minor}"
    archs = torch.cuda.get_arch_list()
    # CUDA cubins are binary-compatible with later minor revisions of the same major
    # architecture, so an sm_60 build runs on an sm_61 GPU (GTX 1060). PTX entries
    # (compute_XY) can be JIT-compiled for any newer GPU.
    compatible = [
        a for a in archs
        if (a.startswith("sm_") and a[3:-1] == str(major) and int(a[-1]) <= minor)
        or (a.startswith("compute_") and int(a[8:]) <= major * 10 + minor)
    ]  # fmt: skip
    if not compatible:
        return False, f"{arch} not covered by torch build arch list {archs}"
    return True, f"{torch.cuda.get_device_name(0)} ({arch}, runs {compatible[-1]} kernels)"


def resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda:0" if cuda_usable()[0] else "cpu"
    if device.startswith("cuda"):
        ok, why = cuda_usable()
        if not ok:
            raise UnsupportedRequest(f"CUDA requested but unusable: {why}")
        return "cuda:0" if device == "cuda" else device
    return device


class TimestralModel:
    """Wraps ``timestral.TimestralForecaster`` behind the ForecastModel protocol."""

    def __init__(
        self,
        size: str,
        model_dir: Path | str | None = None,
        symmetric_averaging: bool = True,
        clip_nonnegative: bool = False,
    ) -> None:
        if size not in SIZES:
            raise ValueError(f"unknown Timestral size {size!r}; expected one of {list(SIZES)}")
        self.size = size
        self.repo_id = SIZES[size]
        self.model_dir = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIR
        # Upstream defaults both to True. We keep symmetric averaging (part of the evaluated
        # forecaster) but default clipping off: our targets (log returns, logits) are signed,
        # and clipping a level series silently would hide behaviour we want to measure.
        self.symmetric_averaging = symmetric_averaging
        self.clip_nonnegative = clip_nonnegative
        self._forecaster = None
        self._device: str | None = None
        self._version = self._read_revision()
        self._native_levels: tuple[float, ...] | None = None

    # -- loading ---------------------------------------------------------------------

    @property
    def local_path(self) -> Path:
        return self.model_dir / self.repo_id.split("/")[1]

    def _read_revision(self) -> str:
        manifest = self.model_dir / "manifest.json"
        if manifest.exists():
            for entry in json.loads(manifest.read_text()).get("models", []):
                if entry.get("repo_id") == self.repo_id:
                    return entry.get("revision", "unknown")
        return "unknown"

    def load(self, device: str = "auto") -> None:
        from timestral import TimestralForecaster

        if self._forecaster is not None:
            return
        dev = resolve_device(device)
        src = self.local_path if (self.local_path / "model.safetensors").exists() else self.repo_id
        self._forecaster = TimestralForecaster.from_pretrained(str(src), device=dev)
        self._device = dev
        self._native_levels = tuple(float(q) for q in self._forecaster.quantile_levels)

    def unload(self) -> None:
        was_cuda = self._device is not None and self._device.startswith("cuda")
        self._forecaster = None
        self._device = None
        gc.collect()
        _trim_heap()
        if was_cuda:
            torch.cuda.synchronize()
            # cuBLAS keeps an 8 MiB (4096*1024*2 + 16*1024*8 bytes) workspace per handle in the
            # caching allocator; it is not model memory, but clear it so unload is verifiable.
            clear = getattr(torch._C, "_cuda_clearCublasWorkspaces", None)
            if clear is not None:
                clear()
            torch.cuda.empty_cache()

    @property
    def is_loaded(self) -> bool:
        return self._forecaster is not None

    @property
    def device(self) -> str | None:
        return self._device

    def metadata(self) -> ModelMetadata:
        known = self._forecaster.supports_known_covariates if self._forecaster is not None else True
        return ModelMetadata(
            name=f"timestral-{self.size.lower()}",
            family="timestral",
            size=self.size,
            version=self._version,
            supports_multivariate=True,
            supports_past_covariates=True,
            supports_future_covariates=known,
            max_context=MAX_CONTEXT,
            max_horizon=MAX_HORIZON,
        )

    # -- inference -------------------------------------------------------------------

    def forecast(self, data: ForecastInput) -> ForecastOutput:
        if self._forecaster is None:
            raise ModelNotLoaded(f"timestral-{self.size} is not loaded")
        meta = self.metadata()
        validate_input(data, meta)
        ctx = truncate_context(data, meta.max_context)

        torch.manual_seed(data.seed)  # inference is deterministic upstream; seeded for safety
        context = ctx.values[None].astype(np.float32)  # (1, V, T)
        past = None if ctx.past_covariates is None else ctx.past_covariates[None].astype(np.float32)
        known = None if ctx.future_covariates is None else ctx.future_covariates[None].astype(np.float32)

        is_cuda = self._device is not None and self._device.startswith("cuda")
        if is_cuda:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        fc = self._forecaster.forecast(
            context,
            prediction_length=int(data.horizon),
            past_covariates=past,
            known_covariates=known,
            symmetric_averaging=self.symmetric_averaging,
            clip_nonnegative=self.clip_nonnegative,
        )
        q = fc.quantiles[0].detach().to("cpu", torch.float64).numpy()  # (V, H, Q)
        if is_cuda:
            torch.cuda.synchronize()
        ms = (time.perf_counter() - t0) * 1000.0

        native = self._native_levels or tuple(fc.quantile_levels)
        levels = resolve_levels(data.quantile_levels, native)
        q_out = interpolate_quantiles(q, native, levels)
        median = q[..., native.index(0.5)]
        return ForecastOutput(
            values=median,
            timestamps=_to_ns(data.future_timestamps),
            quantile_levels=levels,
            quantiles=q_out,
            model=meta,
            inference_ms=ms,
            device=self._device or "cpu",
            input_window=ctx.input_window,
            extra={
                "symmetric_averaging": self.symmetric_averaging,
                "clip_nonnegative": self.clip_nonnegative,
                "quantiles_interpolated": levels != native,
            },
        )
