"""Simple statistical baselines behind the same ForecastModel interface.

Each baseline produces a point path, and quantiles from its own empirical errors: the method is
re-run at up to ``n_origins`` past origins inside the context, and the k-step-ahead errors are
added to the point forecast. So probabilistic metrics compare like with like against Timestral.
Series are handled independently (no cross-series information, no covariates).
"""

from __future__ import annotations

import time

import numpy as np

from mpe.models.base import (
    DEFAULT_QUANTILE_LEVELS,
    ForecastInput,
    ForecastOutput,
    ModelMetadata,
    ModelNotLoaded,
    _to_ns,
    resolve_levels,
    truncate_context,
    validate_input,
)

CODE_VERSION = "baselines-0.1"
MIN_ERRORS = 20


def _ffill(x: np.ndarray) -> np.ndarray:
    """Forward-fill NaN and drop leading NaN."""
    mask = np.isnan(x)
    if not mask.any():
        return x
    idx = np.where(~mask, np.arange(len(x)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = x[idx]
    first = int(np.argmax(~mask))
    return out[first:]


class _Baseline:
    name = "baseline"

    def __init__(self, n_origins: int = 250, max_context: int = 4096) -> None:
        self.n_origins = n_origins
        self.max_context = max_context
        self._loaded = False

    # Subclasses implement the point path from a clean 1-D history.
    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    min_history = 2

    def load(self, device: str = "auto") -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name=self.name,
            family="baseline",
            size=None,
            version=CODE_VERSION,
            supports_multivariate=True,  # applied per series, independently
            supports_past_covariates=False,
            supports_future_covariates=False,
            max_context=self.max_context,
            max_horizon=1024,
        )

    def _errors(self, x: np.ndarray, horizon: int) -> list[np.ndarray]:
        """errors[k] = actual - forecast at step k+1, over past origins inside the context."""
        errs: list[list[float]] = [[] for _ in range(horizon)]
        last_origin = len(x) - 1  # an origin needs at least one realised step after it
        first_origin = max(self.min_history, last_origin - self.n_origins)
        for o in range(first_origin, last_origin):
            p = self.point(x[:o], horizon)
            steps = min(horizon, len(x) - o)
            for k in range(steps):
                errs[k].append(x[o + k] - p[k])
        return [np.asarray(e) for e in errs]

    def _quantiles(self, x: np.ndarray, pt: np.ndarray, levels: tuple[float, ...]) -> np.ndarray:
        horizon = len(pt)
        errs = self._errors(x, horizon)
        base = errs[0] if len(errs[0]) else np.zeros(1)
        out = np.empty((horizon, len(levels)))
        for k in range(horizon):
            e = errs[k]
            if len(e) < MIN_ERRORS:  # too few realised k-step errors: scale 1-step ones
                e = base * np.sqrt(k + 1)
            out[k] = pt[k] + np.quantile(e, levels)
        return np.maximum.accumulate(out, axis=-1)

    def forecast(self, data: ForecastInput) -> ForecastOutput:
        if not self._loaded:
            raise ModelNotLoaded(self.name)
        meta = self.metadata()
        validate_input(data, meta)
        ctx = truncate_context(data, meta.max_context)
        levels = resolve_levels(data.quantile_levels, DEFAULT_QUANTILE_LEVELS)
        if 0.5 not in levels:
            levels = tuple(sorted({*levels, 0.5}))
        t0 = time.perf_counter()
        h = int(data.horizon)
        points, quants = [], []
        for row in ctx.values:
            x = _ffill(row)
            pt = self.point(x, h)
            q = self._quantiles(x, pt, levels)
            points.append(q[:, levels.index(0.5)])  # median of the error-adjusted distribution
            quants.append(q)
        ms = (time.perf_counter() - t0) * 1000.0
        return ForecastOutput(
            values=np.stack(points),
            timestamps=_to_ns(data.future_timestamps),
            quantile_levels=levels,
            quantiles=np.stack(quants),
            model=meta,
            inference_ms=ms,
            device="cpu",
            input_window=ctx.input_window,
            extra={"n_origins": self.n_origins},
        )


class Persistence(_Baseline):
    """Random walk: the last observed value, for every step."""

    name = "persistence"

    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.full(horizon, history[-1])


class Zero(_Baseline):
    """Always 0. On log-return targets this is the price random walk without drift."""

    name = "zero"

    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.zeros(horizon)


class MovingAverage(_Baseline):
    name = "moving_average"

    def __init__(self, window: int = 20, **kw) -> None:
        super().__init__(**kw)
        self.window = window

    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.full(horizon, history[-self.window :].mean())


class Momentum(_Baseline):
    """Last value plus k times the mean change over the last ``lookback`` steps."""

    name = "momentum"
    min_history = 3

    def __init__(self, lookback: int = 20, **kw) -> None:
        super().__init__(**kw)
        self.lookback = lookback

    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:
        d = np.diff(history[-(self.lookback + 1) :])
        drift = d.mean() if len(d) else 0.0
        return history[-1] + drift * np.arange(1, horizon + 1)


class LinearTrend(_Baseline):
    """Least-squares line over the last ``window`` points, extrapolated."""

    name = "linear_trend"
    min_history = 3

    def __init__(self, window: int = 60, **kw) -> None:
        super().__init__(**kw)
        self.window = window

    def point(self, history: np.ndarray, horizon: int) -> np.ndarray:
        y = history[-self.window :]
        n = len(y)
        if n < 2:
            return np.full(horizon, y[-1])
        t = np.arange(n, dtype=np.float64)
        slope, intercept = np.polyfit(t, y, 1)
        return intercept + slope * np.arange(n, n + horizon)


BASELINES = {cls.name: cls for cls in (Zero, Persistence, MovingAverage, Momentum, LinearTrend)}
