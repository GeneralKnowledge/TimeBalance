"""Exercise the adapter offline with a tiny random-weight Timestral network (no download).

Tests may build upstream objects directly; production code still imports timestral only in
src/mpe/models/timestral.py (see test_guards).
"""

import numpy as np
import pytest
import torch

from mpe.fixtures import make_input, synthetic_index
from mpe.models.base import UnsupportedRequest, validate_output
from mpe.models.timestral import TimestralModel

timestral = pytest.importorskip("timestral")


@pytest.fixture(scope="module")
def adapter():
    cfg = timestral.TimestralConfig(
        patch_size=8, d_model=32, num_heads=4, mlp_hidden_dim=64,
        block_schedule=("time", "time_variate", "time", "time_variate"),
        quantile_knots=(0.01, 0.05, *[round(0.1 + 0.05 * i, 2) for i in range(17)], 0.95, 0.99),
        block_size=4, context_length=256,
    )  # fmt: skip
    torch.manual_seed(0)
    net = timestral.TimestralModel(cfg)
    for p in net.parameters():
        torch.nn.init.normal_(p, std=0.05)
    a = TimestralModel("5M")
    a._forecaster = timestral.TimestralForecaster(net.eval())
    a._device = "cpu"
    a._native_levels = tuple(cfg.quantile_knots)
    return a


def series(v=1, n=200, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((v, n)).cumsum(-1).squeeze()


@pytest.mark.parametrize("h", [1, 8, 20])
def test_univariate_contract(adapter, h):
    out = adapter.forecast(make_input(series(), synthetic_index(200), h))
    validate_output(out, 1, h)
    assert len(out.quantile_levels) == 21 and out.device == "cpu"
    assert out.model.name == "timestral-5m"


def test_multivariate_and_covariates(adapter):
    x = series(v=3)
    inp = make_input(
        x, synthetic_index(200), 10, names=("a", "b", "c"),
        past_covariates=np.random.default_rng(1).standard_normal((2, 200)),
        future_covariates=(np.arange(210) % 7 == 0).astype(float)[None],
    )  # fmt: skip
    out = adapter.forecast(inp)
    validate_output(out, 3, 10)


def test_deterministic_on_cpu(adapter):
    inp = make_input(series(seed=3), synthetic_index(200), 12)
    a, b = adapter.forecast(inp), adapter.forecast(inp)
    np.testing.assert_array_equal(a.quantiles, b.quantiles)


def test_custom_levels_interpolated_and_extrapolation_refused(adapter):
    inp = make_input(series(), synthetic_index(200), 4, quantile_levels=(0.025, 0.5, 0.975))
    out = adapter.forecast(inp)
    assert out.quantile_levels == (0.025, 0.5, 0.975) and out.extra["quantiles_interpolated"]
    validate_output(out, 1, 4)
    with pytest.raises(UnsupportedRequest):
        adapter.forecast(make_input(series(), synthetic_index(200), 4, quantile_levels=(0.001, 0.5)))


def test_long_context_truncated(adapter):
    n = 40_000
    out = adapter.forecast(make_input(np.sin(np.arange(n) / 10.0), synthetic_index(n), 2))
    assert out.input_window["truncated"] and out.input_window["length"] == 32_768
