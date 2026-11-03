import numpy as np
import pytest

from mpe.features.transforms import inv_logit, log_returns, logit, reconstruct_prices


def test_log_returns_round_trip():
    p = np.array([100.0, 101.0, 99.5, 102.25])
    r = log_returns(p)
    assert r.shape == (3,)
    np.testing.assert_allclose(reconstruct_prices(p[0], r), p[1:])


def test_log_returns_reject_non_positive():
    with pytest.raises(ValueError):
        log_returns(np.array([1.0, 0.0, 2.0]))


@pytest.mark.parametrize("eps", [1e-4, 1e-2])
def test_logit_clips_and_inverts(eps):
    p = np.array([0.0, eps / 2, 0.3, 0.5, 0.97, 1.0])
    z = logit(p, eps)
    assert np.isfinite(z).all()
    back = inv_logit(z, eps)
    np.testing.assert_allclose(back, np.clip(p, eps, 1 - eps), atol=1e-12)


def test_inv_logit_strictly_inside_unit_interval_for_extremes():
    z = np.array([-1e6, -800.0, -40.0, 0.0, 40.0, 800.0, 1e6])
    p = inv_logit(z)
    assert ((p > 0) & (p < 1)).all()
    assert np.all(np.diff(p) >= 0)


def test_monotone_transform_keeps_quantile_order():
    zq = np.sort(np.random.default_rng(0).standard_normal((5, 21)) * 5, axis=-1)
    assert (np.diff(inv_logit(zq), axis=-1) >= 0).all()


def test_bad_eps():
    with pytest.raises(ValueError):
        logit(np.array([0.5]), eps=0.6)
