"""Model-agnostic forecasting interface.

Every forecasting model (Timestral sizes, baselines, later foundation models) implements
:class:`ForecastModel`. Nothing outside ``mpe.models.timestral`` knows about Timestral.

Array conventions:
    values             (T,) univariate or (V, T) multivariate; NaN marks a missing value
    timestamps         (T,) datetime64, strictly increasing
    past_covariates    (C_p, T)          observed only up to the input cutoff
    future_covariates  (C_f, T + horizon) genuinely known ahead (calendar features etc.)
    output values      (V, horizon)       median
    output quantiles   (V, horizon, Q)    non-decreasing along Q
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import numpy as np

DEFAULT_QUANTILE_LEVELS: tuple[float, ...] = (
    0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
    0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99,
)  # fmt: skip


class InvalidForecastInput(ValueError):
    """The request is malformed or would leak information past the input cutoff."""


class UnsupportedRequest(ValueError):
    """The request is valid but the model cannot honour it (e.g. covariates on a baseline)."""


class ModelNotLoaded(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelMetadata:
    name: str  # 'timestral-209m', 'persistence'
    family: str  # 'timestral' | 'baseline'
    size: str | None  # '209M'
    version: str  # HF revision SHA or code version
    supports_multivariate: bool
    supports_past_covariates: bool
    supports_future_covariates: bool
    max_context: int
    max_horizon: int


@dataclass(frozen=True)
class ForecastInput:
    values: np.ndarray
    timestamps: np.ndarray
    series_names: Sequence[str]
    horizon: int
    input_cutoff: datetime
    future_timestamps: np.ndarray
    past_covariates: np.ndarray | None = None
    future_covariates: np.ndarray | None = None
    covariate_names: Sequence[str] = ()
    quantile_levels: Sequence[float] | None = None  # None = model default
    seed: int = 0

    @property
    def values_2d(self) -> np.ndarray:
        v = np.asarray(self.values, dtype=np.float64)
        return v[None, :] if v.ndim == 1 else v

    @property
    def n_series(self) -> int:
        return self.values_2d.shape[0]


@dataclass(frozen=True)
class ForecastOutput:
    values: np.ndarray  # (V, horizon) median
    timestamps: np.ndarray  # (horizon,)
    quantile_levels: tuple[float, ...]
    quantiles: np.ndarray | None  # (V, horizon, Q)
    model: ModelMetadata
    inference_ms: float
    device: str  # 'cpu' | 'cuda:0'
    input_window: dict  # {'length', 'start', 'end', 'truncated'}
    extra: dict = field(default_factory=dict)

    def quantile(self, level: float) -> np.ndarray:
        """(V, horizon) forecast at one of the output's quantile levels."""
        for i, q in enumerate(self.quantile_levels):
            if abs(q - level) < 1e-9:
                assert self.quantiles is not None
                return self.quantiles[..., i]
        raise KeyError(f"level {level} not in {self.quantile_levels}")


@runtime_checkable
class ForecastModel(Protocol):
    def load(self, device: str = "auto") -> None: ...
    def forecast(self, data: ForecastInput) -> ForecastOutput: ...
    def unload(self) -> None: ...
    def metadata(self) -> ModelMetadata: ...
    @property
    def is_loaded(self) -> bool: ...


# --------------------------------------------------------------------------------------
# Validation helpers shared by every model
# --------------------------------------------------------------------------------------


def _to_ns(ts: np.ndarray) -> np.ndarray:
    try:
        return np.asarray(ts).astype("datetime64[ns]")
    except (TypeError, ValueError) as e:
        raise InvalidForecastInput(f"timestamps must be datetime64-convertible: {e}") from e


def _cutoff_ns(cutoff: datetime) -> np.datetime64:
    if not isinstance(cutoff, datetime):
        raise InvalidForecastInput("input_cutoff must be a datetime")
    if cutoff.tzinfo is None:
        raise InvalidForecastInput("input_cutoff must be timezone-aware (UTC)")
    naive_utc = cutoff.astimezone(UTC).replace(tzinfo=None)
    return np.datetime64(naive_utc, "ns")


def validate_input(data: ForecastInput, meta: ModelMetadata) -> None:
    """Raise InvalidForecastInput / UnsupportedRequest; never silently drop anything."""
    values = np.asarray(data.values)
    if values.ndim not in (1, 2):
        raise InvalidForecastInput(f"values must be (T,) or (V, T), got shape {values.shape}")
    if not np.issubdtype(values.dtype, np.number):
        raise InvalidForecastInput("values must be numeric")
    v2 = data.values_2d
    n_series, t = v2.shape
    if t < 2:
        raise InvalidForecastInput("need at least 2 context points")
    if np.isinf(v2).any():
        raise InvalidForecastInput("values contain inf; use NaN for missing")
    if np.isnan(v2).all(axis=1).any():
        raise InvalidForecastInput("a series is entirely missing")
    if len(data.series_names) != n_series:
        raise InvalidForecastInput(f"series_names has {len(data.series_names)} names for {n_series} series")
    if n_series > 1 and not meta.supports_multivariate:
        raise UnsupportedRequest(f"{meta.name} does not support multivariate targets")

    ts = _to_ns(data.timestamps)
    if ts.shape != (t,):
        raise InvalidForecastInput(f"timestamps must be ({t},), got {ts.shape}")
    if np.isnat(ts).any():
        raise InvalidForecastInput("timestamps contain NaT")
    if not (np.diff(ts) > np.timedelta64(0, "ns")).all():
        raise InvalidForecastInput("timestamps must be strictly increasing")

    cutoff = _cutoff_ns(data.input_cutoff)
    if ts[-1] > cutoff:
        n_late = int((ts > cutoff).sum())
        raise InvalidForecastInput(f"look-ahead: {n_late} context points are after input_cutoff")

    if not isinstance(data.horizon, (int, np.integer)) or data.horizon < 1:
        raise InvalidForecastInput(f"horizon must be an int >= 1, got {data.horizon!r}")
    if data.horizon > meta.max_horizon:
        raise UnsupportedRequest(f"horizon {data.horizon} exceeds {meta.name} max_horizon {meta.max_horizon}")

    fts = _to_ns(data.future_timestamps)
    if fts.shape != (data.horizon,):
        raise InvalidForecastInput(f"future_timestamps must be ({data.horizon},), got {fts.shape}")
    if (fts <= cutoff).any():
        raise InvalidForecastInput("future_timestamps must be after input_cutoff")
    if data.horizon > 1 and not (np.diff(fts) > np.timedelta64(0, "ns")).all():
        raise InvalidForecastInput("future_timestamps must be strictly increasing")

    n_cov = 0
    if data.past_covariates is not None:
        if not meta.supports_past_covariates:
            raise UnsupportedRequest(f"{meta.name} does not support past covariates")
        pc = np.asarray(data.past_covariates, dtype=np.float64)
        if pc.ndim != 2 or pc.shape[1] != t:
            raise InvalidForecastInput(f"past_covariates must be (C_p, {t}), got {pc.shape}")
        if np.isinf(pc).any():
            raise InvalidForecastInput("past_covariates contain inf")
        n_cov += pc.shape[0]
    if data.future_covariates is not None:
        if not meta.supports_future_covariates:
            raise UnsupportedRequest(f"{meta.name} does not support known-future covariates")
        fc = np.asarray(data.future_covariates, dtype=np.float64)
        if fc.ndim != 2 or fc.shape[1] != t + data.horizon:
            raise InvalidForecastInput(f"future_covariates must be (C_f, {t + data.horizon}), got {fc.shape}")
        if np.isinf(fc).any():
            raise InvalidForecastInput("future_covariates contain inf")
        n_cov += fc.shape[0]
    if data.covariate_names and len(data.covariate_names) != n_cov:
        raise InvalidForecastInput(f"covariate_names has {len(data.covariate_names)} names for {n_cov} rows")

    if data.quantile_levels is not None:
        q = np.asarray(data.quantile_levels, dtype=np.float64)
        if q.ndim != 1 or len(q) == 0 or (q <= 0).any() or (q >= 1).any():
            raise InvalidForecastInput("quantile_levels must be in (0, 1)")
        if not (np.diff(q) > 0).all():
            raise InvalidForecastInput("quantile_levels must be strictly increasing")


@dataclass(frozen=True)
class PreparedContext:
    values: np.ndarray  # (V, T') float64, NaN = missing
    past_covariates: np.ndarray | None  # (C_p, T')
    future_covariates: np.ndarray | None  # (C_f, T' + H)
    input_window: dict


def truncate_context(data: ForecastInput, max_context: int) -> PreparedContext:
    """Keep the most recent ``max_context`` points and record whether anything was cut."""
    v = data.values_2d
    t = v.shape[1]
    ts = _to_ns(data.timestamps)
    start = max(0, t - max_context)
    pc = None if data.past_covariates is None else np.asarray(data.past_covariates, np.float64)[:, start:]
    fc = None if data.future_covariates is None else np.asarray(data.future_covariates, np.float64)[:, start:]
    window = {
        "length": t - start,
        "start": str(ts[start]),
        "end": str(ts[-1]),
        "truncated": start > 0,
        "original_length": t,
    }
    return PreparedContext(v[:, start:], pc, fc, window)


def resolve_levels(requested: Sequence[float] | None, native: Sequence[float]) -> tuple[float, ...]:
    return tuple(float(q) for q in (native if requested is None else requested))


def interpolate_quantiles(
    quantiles: np.ndarray, native: Sequence[float], requested: Sequence[float]
) -> np.ndarray:
    """Map (..., Q_native) to (..., Q_requested) by linear interpolation between native levels.

    Levels outside [min(native), max(native)] would be extrapolation and are refused.
    """
    native_arr = np.asarray(native, dtype=np.float64)
    req = np.asarray(requested, dtype=np.float64)
    if np.array_equal(native_arr, req):
        return quantiles
    if req.min() < native_arr.min() - 1e-12 or req.max() > native_arr.max() + 1e-12:
        raise UnsupportedRequest(
            f"quantile levels must lie within [{native_arr.min()}, {native_arr.max()}]; got {list(req)}"
        )
    flat = quantiles.reshape(-1, quantiles.shape[-1])
    out = np.stack([np.interp(req, native_arr, row) for row in flat])
    return out.reshape(*quantiles.shape[:-1], len(req))


def validate_output(out: ForecastOutput, n_series: int, horizon: int) -> None:
    """Assert the contract every model must meet. Raises AssertionError on violation."""
    assert out.values.shape == (n_series, horizon), f"values shape {out.values.shape}"
    assert np.isfinite(out.values).all(), "non-finite point forecast"
    assert out.timestamps.shape == (horizon,)
    if out.quantiles is not None:
        assert out.quantiles.shape == (n_series, horizon, len(out.quantile_levels)), out.quantiles.shape
        assert np.isfinite(out.quantiles).all(), "non-finite quantiles"
        assert (np.diff(out.quantiles, axis=-1) >= -1e-9).all(), "quantiles decrease along Q"
