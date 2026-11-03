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


def test_interval_score_hand_calculated():
    # 90% interval [0, 2]; a = 0.1 so a miss costs 2/0.1 = 20 per unit outside
    s = M.interval_score(np.array([1.0, -0.5, 3.0]), np.zeros(3), np.full(3, 2.0), 0.9)
    assert s.tolist() == pytest.approx([2.0, 2.0 + 20 * 0.5, 2.0 + 20 * 1.0])


def test_pit_histogram():
    levels = np.array([0.25, 0.5, 0.75])
    # outcomes: one below every quantile, one between 0.5 and 0.75, two above all
    below = np.array([[True, True, True], [False, False, True], [False, False, False], [False, False, False]])
    h = M.pit_histogram(below, levels)
    assert h["observed"] == pytest.approx([0.25, 0.0, 0.25, 0.5])
    assert h["expected"] == pytest.approx([0.25, 0.25, 0.25, 0.25])
    assert h["tv_distance"] == pytest.approx(0.25)


def test_diebold_mariano_hand_calculated():
    d = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    r = M.diebold_mariano(d, h=1)
    # mean 3, gamma_0 = 2, stat = 3 / sqrt(2 / 5); HLN factor sqrt((5 + 1 - 2) / 5)
    expected = 3 / math.sqrt(2 / 5) * math.sqrt(4 / 5)
    assert r["statistic"] == pytest.approx(expected)
    assert r["pvalue"] == pytest.approx(math.erfc(expected / math.sqrt(2)))
    # one lag: e = d - 3; gamma_1 = sum e_t e_{t-1} / n = (2 + 0 + 0 + 2) / 5 = 0.8
    assert M.newey_west_variance(d, 1) == pytest.approx(2.8)  # 2 + 2 * (1 - 1/2) * 0.8
    assert math.isnan(M.diebold_mariano(d[:3], 1)["pvalue"])  # too short
    flat = M.diebold_mariano(np.zeros(10), 1)
    assert flat["statistic"] == 0 and flat["pvalue"] == 1


def test_holm_adjustment():
    adj = M.holm([0.01, 0.04, float("nan"), 0.03])
    # sorted 0.01, 0.03, 0.04 with m = 3: 0.03, 0.06, max(0.06, 0.04) = 0.06
    assert adj[0] == pytest.approx(0.03) and adj[3] == pytest.approx(0.06) and adj[1] == pytest.approx(0.06)
    assert math.isnan(adj[2])
