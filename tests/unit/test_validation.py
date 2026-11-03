from dataclasses import replace
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from mpe.fixtures import make_input, synthetic_index
from mpe.models.base import (
    InvalidForecastInput,
    UnsupportedRequest,
    interpolate_quantiles,
    truncate_context,
    validate_input,
)
from mpe.models.baselines import Persistence

META = Persistence().metadata()


def good(n=100, h=5, **kw):
    x = np.random.default_rng(0).standard_normal(n).cumsum()
    return make_input(x, synthetic_index(n), h, **kw)


def test_good_input_passes():
    validate_input(good(), META)


def test_leakage_rejected_when_context_after_cutoff():
    inp = good()
    early = inp.input_cutoff - timedelta(hours=3)
    with pytest.raises(InvalidForecastInput, match="look-ahead"):
        validate_input(replace(inp, input_cutoff=early, future_timestamps=inp.future_timestamps), META)


def test_future_timestamps_must_follow_cutoff():
    inp = good()
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, future_timestamps=inp.timestamps[-5:]), META)


def test_naive_cutoff_rejected():
    inp = good()
    with pytest.raises(InvalidForecastInput, match="timezone"):
        validate_input(replace(inp, input_cutoff=inp.input_cutoff.replace(tzinfo=None)), META)


@pytest.mark.parametrize("h", [0, -1])
def test_bad_horizon(h):
    inp = good()
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, horizon=h), META)


def test_horizon_above_max_is_unsupported():
    inp = good(h=5)
    with pytest.raises(UnsupportedRequest):
        validate_input(replace(inp, horizon=5000, future_timestamps=np.arange(5000)), META)


def test_non_monotonic_timestamps():
    inp = good()
    ts = inp.timestamps.copy()
    ts[[10, 11]] = ts[[11, 10]]
    with pytest.raises(InvalidForecastInput, match="increasing"):
        validate_input(replace(inp, timestamps=ts), META)


def test_shape_errors():
    inp = good()
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, values=np.zeros((2, 3, 4))), META)
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, timestamps=inp.timestamps[:-1]), META)
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, series_names=("a", "b")), META)


def test_inf_and_all_nan_rejected():
    inp = good()
    v = inp.values.copy()
    v[3] = np.inf
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, values=v), META)
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, values=np.full(100, np.nan)), META)


def test_covariates_on_baseline_are_refused_not_dropped():
    inp = good()
    with pytest.raises(UnsupportedRequest):
        validate_input(replace(inp, past_covariates=np.zeros((1, 100))), META)
    with pytest.raises(UnsupportedRequest):
        validate_input(replace(inp, future_covariates=np.zeros((1, 105))), META)


def test_covariate_shapes_checked_when_supported():
    meta = replace(META, supports_past_covariates=True, supports_future_covariates=True)
    inp = good()
    validate_input(
        replace(inp, past_covariates=np.zeros((2, 100)), future_covariates=np.zeros((1, 105))), meta
    )
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, past_covariates=np.zeros((2, 99))), meta)
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, future_covariates=np.zeros((1, 100))), meta)  # must cover the horizon
    with pytest.raises(InvalidForecastInput):
        validate_input(replace(inp, past_covariates=np.zeros((2, 100)), covariate_names=("a",)), meta)


def test_quantile_levels_validated():
    inp = good()
    for bad in [(0.0, 0.5), (0.5, 1.0), (0.9, 0.1)]:
        with pytest.raises(InvalidForecastInput):
            validate_input(replace(inp, quantile_levels=bad), META)


def test_truncation_keeps_most_recent_and_records_it():
    inp = good(n=100)
    ctx = truncate_context(inp, 30)
    assert ctx.values.shape == (1, 30)
    np.testing.assert_array_equal(ctx.values[0], inp.values[-30:])
    assert ctx.input_window["truncated"] and ctx.input_window["original_length"] == 100
    assert not truncate_context(inp, 1000).input_window["truncated"]


def test_interpolate_quantiles():
    native = (0.1, 0.5, 0.9)
    q = np.array([[[1.0, 2.0, 4.0]]])
    np.testing.assert_allclose(interpolate_quantiles(q, native, (0.3, 0.5, 0.7)), [[[1.5, 2.0, 3.0]]])
    with pytest.raises(UnsupportedRequest):
        interpolate_quantiles(q, native, (0.05, 0.5))


def test_make_input_cutoff_is_last_timestamp():
    inp = good()
    assert pd.Timestamp(inp.timestamps[-1]).tz_localize("UTC") == pd.Timestamp(inp.input_cutoff)
