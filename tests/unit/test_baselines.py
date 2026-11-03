import numpy as np
import pytest

from mpe.fixtures import make_input, sine_noise, synthetic_index
from mpe.models.base import ModelNotLoaded, validate_output
from mpe.models.baselines import BASELINES, Persistence
from mpe.models.registry import ModelManager


@pytest.mark.parametrize("name", sorted(BASELINES))
@pytest.mark.parametrize("h", [1, 7, 30])
def test_output_contract(name, h):
    m = BASELINES[name]()
    m.load()
    x = np.random.default_rng(1).standard_normal(300).cumsum()
    out = m.forecast(make_input(x, synthetic_index(300), h))
    validate_output(out, 1, h)
    assert out.quantile_levels[10] == 0.5 and len(out.quantile_levels) == 21
    assert out.model.family == "baseline"


def test_multivariate_rows_independent():
    m = Persistence()
    m.load()
    x = np.vstack([np.arange(50.0), -np.arange(50.0)])
    out = m.forecast(make_input(x, synthetic_index(50), 3, names=("a", "b")))
    validate_output(out, 2, 3)
    np.testing.assert_allclose(
        out.values[:, 0], [49 + 1, -49 - 1], atol=1e-9
    )  # constant diffs, so error is +-1


def test_custom_levels_and_nan_handling():
    m = BASELINES["moving_average"]()
    m.load()
    x = np.random.default_rng(2).standard_normal(200)
    x[[5, 50, 199]] = np.nan
    out = m.forecast(make_input(x, synthetic_index(200), 4, quantile_levels=(0.1, 0.9)))
    assert out.quantile_levels == (0.1, 0.5, 0.9)
    validate_output(out, 1, 4)


def test_linear_trend_recovers_line():
    m = BASELINES["linear_trend"]()
    m.load()
    x = 3.0 + 0.5 * np.arange(200)
    out = m.forecast(make_input(x, synthetic_index(200), 5))
    np.testing.assert_allclose(out.values[0], 3.0 + 0.5 * np.arange(200, 205), atol=1e-6)


def test_sine_fixture_quantiles_cover_truth():
    df = sine_noise()
    m = BASELINES["persistence"]()
    m.load()
    out = m.forecast(make_input(df["value"].to_numpy()[:1000], synthetic_index(1000), 1))
    truth = df["noiseless"].iloc[1000]
    assert out.quantile(0.01)[0, 0] <= truth <= out.quantile(0.99)[0, 0]


def test_not_loaded():
    with pytest.raises(ModelNotLoaded):
        Persistence().forecast(make_input(np.arange(10.0), synthetic_index(10), 1))


def test_manager_lru_unloads():
    mgr = ModelManager(max_resident=1)
    a = mgr.get("persistence")
    assert a.is_loaded
    b = mgr.get("momentum")
    assert b.is_loaded and not a.is_loaded and mgr.resident == ["momentum"]
    mgr2 = ModelManager(max_resident=2)
    mgr2.get("persistence"), mgr2.get("momentum")
    mgr2.get("persistence")  # touch
    mgr2.get("linear_trend")
    assert mgr2.resident == ["persistence", "linear_trend"]
    mgr2.release_all()
    assert mgr2.resident == []
    with pytest.raises(KeyError):
        mgr.get("nope")
