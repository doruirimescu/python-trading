import numpy as np
import pytest

from perfectshape.config import RunConfig, ScoringConfig
from perfectshape.data.panel import align
from perfectshape.pipeline import scan
from perfectshape.shapes import get_shape, linear_fit, zone_swings
from perfectshape.solver import Bounds, Solver, project_weights

T = 300
tau = np.linspace(0, 1, T)
SC = ScoringConfig()


def test_linear_fit_exact_line():
    Y = np.column_stack([1 + 0.5 * tau, 2 - 0.3 * tau])
    a, b, resid, r2 = linear_fit(Y)
    np.testing.assert_allclose(b, [0.5, -0.3], atol=1e-12)
    np.testing.assert_allclose(r2, 1.0)
    assert np.abs(resid).max() < 1e-12


def test_trend_scores_rank_shapes():
    rng = np.random.default_rng(0)
    straight = np.exp(0.4 * tau)
    noisy = np.exp(0.4 * tau + np.cumsum(rng.normal(0, 0.02, T)))
    falling = np.exp(-0.4 * tau)
    flat = 1 + 0.001 * np.sin(tau * 20)
    up = get_shape("uptrend").score(np.column_stack([straight, noisy, falling, flat]), SC)
    assert up.score[0] > 0.99
    assert up.score[0] > up.score[1]
    assert up.score[2] == 0 and up.score[3] == 0          # wrong direction / too flat are gated
    down = get_shape("downtrend").score(np.column_stack([falling, straight]), SC)
    assert down.score[0] > 0.99 and down.score[1] == 0


def test_range_score_prefers_oscillation_over_drift():
    sine = 1 + 0.1 * np.sin(2 * np.pi * tau * 4)
    drift = 1 + 0.3 * tau + 0.02 * np.sin(2 * np.pi * tau * 4)
    r = get_shape("range").score(np.column_stack([sine, drift]), SC)
    assert r.score[0] > 0.8 and r.score[1] == 0
    assert zone_swings(np.log(sine)[:, None])[0] >= 7


def test_project_weights_bounds():
    W = project_weights(np.array([[1.4, -0.2, -0.2], [0.2, 0.3, 0.5]]), Bounds(True, 0.7))
    np.testing.assert_allclose(W.sum(axis=1), 1)
    assert (W >= 0).all() and (W <= 0.7 + 1e-9).all()


def test_trend_solver_recovers_hedged_pair():
    rng = np.random.default_rng(1)
    wander = np.cumsum(rng.normal(0, 0.01, T))
    target = 1 + 0.5 * tau
    X = np.column_stack([target + wander, target - wander, 1 + np.cumsum(rng.normal(0, 0.01, T))])
    X /= X[0]
    s = Solver(X, "trend_tstat", direction=1)
    W = s.solve([0], np.array([1, 2]), Bounds(True, 0.7))
    np.testing.assert_allclose(W[0], [0.5, 0.5], atol=0.02)


def test_range_solver_cancels_drift():
    rng = np.random.default_rng(2)
    osc = 0.1 * np.sin(2 * np.pi * tau * 5)
    drift = 0.6 * tau
    X = np.column_stack([1 + osc + drift, 1 + osc - drift + rng.normal(0, 1e-3, T)])
    s = Solver(X, "range_ratio")
    W = s.solve([0], np.array([1]), Bounds(True, 0.7))
    np.testing.assert_allclose(W[0], [0.5, 0.5], atol=0.05)


def test_align_ffill_limited():
    d = np.arange("2024-01-01", "2024-01-11", dtype="datetime64[D]")
    a = (d, np.arange(10.0) + 1)
    b = (np.delete(d, [3, 6, 7, 8]), np.arange(6.0) + 1)
    p = align({"A": a, "B": b}, max_gap_bars=1)
    col = p.close[:, 1]
    assert np.isfinite(col[3])                       # 1-bar hole filled
    assert np.isnan(col[7]) and np.isnan(col[8])     # 3-bar hole not


@pytest.fixture(scope="module")
def planted():
    tickers = [f"S{i:02d}" for i in range(30)]
    plant = {"uptrend": ["S03", "S17"], "downtrend": ["S08", "S22"], "range": ["S11", "S26"]}
    cfg = RunConfig.model_validate({
        "universe": {"tickers": tickers},
        "data": {"source": "synthetic", "years": 6,
                 "synthetic": {"n_bars": 1600, "seed": 3, "plant": plant}},
        "search": {"windows": [126, 252, 504, 1008], "seeds": 30, "max_assets": 3},
    })
    return scan(cfg), plant


@pytest.mark.parametrize("shape", ["uptrend", "downtrend", "range"])
def test_scan_finds_planted_pair(planted, shape):
    out, plant = planted
    tops = out.ranked[shape][:3] if shape == "range" else out.ranked[shape][:1]   # random walks also form ranges
    hit = [r for r in tops if set(r.basket.members) == set(plant[shape])]
    assert hit, [r.basket.members for r in out.ranked[shape][:5]]
    assert hit[0].duration == 1008 and hit[0].alive
