"""Hand-checked metric implementations (mpe.research.metrics)."""

import math

import numpy as np
import pytest

from mpe.research import metrics as M


def test_point_summary_hand_calculated():
    # forecasts 1, 2, 4 for actuals 2, 2, 1: errors (forecast - actual) = -1, 0, 3
    s = M.point_summary(np.array([1.0, 2.0, 4.0]) - np.array([2.0, 2.0, 1.0]))
    assert s["n"] == 3
    assert s["mae"] == pytest.approx(4 / 3)
    assert s["mse"] == pytest.approx(10 / 3)
    assert s["rmse"] == pytest.approx(math.sqrt(10 / 3))
    assert s["mean_error"] == pytest.approx(2 / 3)  # positive = over-forecasting


def test_point_summary_empty_is_nan_not_zero():
    s = M.point_summary(np.array([]))
    assert s["n"] == 0 and math.isnan(s["mae"])


def test_directional_accuracy_excludes_zero_changes():
    pred = np.array([0.1, -0.2, 0.3, 0.0, 0.5, -0.1])
    act = np.array([0.2, 0.1, 0.0, 0.4, 0.1, -0.3])
    d = M.directional(pred, act)
    # valid pairs: (0.1, 0.2) hit, (-0.2, 0.1) miss, (0.5, 0.1) hit, (-0.1, -0.3) hit
    assert (d["hits"], d["n"]) == (3, 4)
    assert d["accuracy"] == pytest.approx(0.75)
    assert d["actual_zero"] == 1 and d["pred_zero"] == 1


def test_directional_all_zero_is_nan():
    d = M.directional(np.zeros(3), np.zeros(3))
    assert d["n"] == 0 and math.isnan(d["accuracy"])


def test_pinball_hand_calculated():
    y = np.array([1.0])
    q = np.array([[0.0, 1.0, 3.0]])
    levels = np.array([0.1, 0.5, 0.9])
    pl = M.pinball(y, q, levels)
    # tau=0.1, y-q=1: 0.1*1; tau=0.5, y-q=0: 0; tau=0.9, y-q=-2: (0.9-1)*-2 = 0.2
    assert pl[0] == pytest.approx([0.1, 0.0, 0.2])


def test_crps_quantile_trapezoid_hand_calculated():
    y = np.array([1.0])
    q = np.array([[0.0, 1.0, 3.0]])
    levels = np.array([0.1, 0.5, 0.9])
    # 2 * [ (0.1 + 0)/2 * 0.4 + (0 + 0.2)/2 * 0.4 ] = 2 * (0.02 + 0.04) = 0.12
    assert M.crps_quantile(y, q, levels)[0] == pytest.approx(0.12)


def test_crps_quantile_approaches_closed_form_inside_level_range():
    # For a standard normal forecast and y = 0, CRPS restricted to tau in [a, 1-a] converges to
    # the truncated integral; with dense levels covering (0, 1) it approaches the closed form
    # 2*phi(0) - 1/sqrt(pi) = 0.2337 (from below, because tails are omitted).
    from statistics import NormalDist

    levels = np.linspace(0.001, 0.999, 999)
    q = np.array([[NormalDist().inv_cdf(t) for t in levels]])
    approx = M.crps_quantile(np.array([0.0]), q, levels)[0]
    exact = 2 * NormalDist().pdf(0) - 1 / math.sqrt(math.pi)
    assert approx < exact
    assert approx == pytest.approx(exact, abs=2e-3)


def test_crps_needs_increasing_levels():
    with pytest.raises(ValueError):
        M.crps_quantile(np.array([0.0]), np.array([[0.0, 1.0]]), np.array([0.5, 0.4]))


def test_interval_coverage_and_width():
    levels = [0.05, 0.25, 0.5, 0.75, 0.95]
    lo, hi = M.central_interval(levels, 0.9)
    assert (levels[lo], levels[hi]) == (0.05, 0.95)
    lo50, hi50 = M.central_interval(levels, 0.5)
    assert (levels[lo50], levels[hi50]) == (0.25, 0.75)
    y = np.array([0.0, 1.0, 2.0, -5.0])
    a, b = np.array([-1.0, 1.0, 0.0, -1.0]), np.array([1.0, 2.0, 1.0, 1.0])
    cov = M.covered(y, a, b)
    assert cov.tolist() == [True, True, False, False]  # closed interval: 1.0 in [1, 2]
    with pytest.raises(ValueError):
        M.central_interval(levels, 0.8)  # 0.1 / 0.9 not available: never interpolated silently


def test_quantile_calibration_error():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    q = np.array([[0.5, 2.5]] * 4)  # levels 0.25, 0.75
    c = M.quantile_calibration(y, q, np.array([0.25, 0.75]))
    assert c["frequency"] == [0.25, 0.75]
    assert c["qce"] == pytest.approx(0.0)
    c2 = M.quantile_calibration(y, np.array([[3.5, 3.6]] * 4), np.array([0.25, 0.75]))
    assert c2["qce"] == pytest.approx((0.75 + 0.25) / 2)


def test_block_bootstrap_constant_series_and_reproducibility():
    lo, hi = M.moving_block_bootstrap_mean(np.full(50, 0.3), block=5, samples=200, seed=1)
    assert lo == pytest.approx(0.3) and hi == pytest.approx(0.3)
    rng = np.random.default_rng(0)
    d = rng.normal(1.0, 1.0, 400)
    a = M.moving_block_bootstrap_mean(d, 10, 500, seed=7)
    b = M.moving_block_bootstrap_mean(d, 10, 500, seed=7)
    assert a == b and a[0] < d.mean() < a[1]
