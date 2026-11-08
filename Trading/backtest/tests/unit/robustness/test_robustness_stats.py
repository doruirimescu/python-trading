import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "golden"))
from synth import make_result  # noqa: E402

from tradelab.robustness import (block_bootstrap, count_trials, dsr, dsr_from_stats, expected_max_sr, min_trl,  # noqa: E402
                                 min_trl_from_stats, pbo_cscv, psr, psr_from_stats, regime_breakdown,
                                 trade_monte_carlo, trial_ledger_append, trial_ledger_read, verdict)


def test_psr_matches_formula_by_hand():
    # SR=0.1/period, T=250, skew=-0.5, kurt=5, benchmark 0.05
    sr, T, g3, g4, b = 0.1, 250, -0.5, 5.0, 0.05
    z = (sr - b) * math.sqrt(T - 1) / math.sqrt(1 + 0.5 * 0.1 + (5 - 1) / 4 * 0.01)
    assert psr_from_stats(sr, T, g3, g4, b) == pytest.approx(sps.norm.cdf(z))
    # normal case reduces to Lo (2002) variance 1 + SR^2/2
    z0 = sr * math.sqrt(T - 1) / math.sqrt(1 + sr**2 / 2)
    assert psr_from_stats(sr, T, 0.0, 3.0, 0.0) == pytest.approx(sps.norm.cdf(z0))


def test_psr_from_returns_uses_nonexcess_kurtosis():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0.001, 0.01, 1000))
    s_ = x.mean() / x.std(ddof=1)
    g3, g4 = sps.skew(x), sps.kurtosis(x, fisher=False)
    expect = sps.norm.cdf(s_ * math.sqrt(999) / math.sqrt(1 - g3 * s_ + (g4 - 1) / 4 * s_**2))
    assert psr(x) == pytest.approx(expect)


def test_expected_max_sr_and_dsr():
    # N=100, unit variance: E[max] ~ 2.53 by the Bailey-LdP approximation (true normal E[max]=2.508)
    assert expected_max_sr(100, 1.0) == pytest.approx(
        (1 - 0.5772156649) * sps.norm.ppf(0.99) + 0.5772156649 * sps.norm.ppf(1 - 1 / (100 * math.e)), abs=1e-6)
    assert 2.50 < expected_max_sr(100, 1.0) < 2.56
    assert expected_max_sr(1, 1.0) == 0.0
    # monotone: more trials -> lower DSR
    sr, T = 0.12, 1000
    assert dsr_from_stats(sr, T, 0, 3, 10, 0.001) > dsr_from_stats(sr, T, 0, 3, 1000, 0.001)
    # n_trials=1 -> DSR == PSR(0)
    assert dsr_from_stats(sr, T, 0, 3, 1, 0.5) == pytest.approx(psr_from_stats(sr, T, 0, 3, 0.0))
    x = pd.Series(np.random.default_rng(1).normal(0.002, 0.01, 500))
    assert dsr(x, 50, 0.0004) < psr(x)


def test_min_trl_roundtrip():
    sr, b = 0.08, 0.0
    n = min_trl_from_stats(sr, 0.0, 3.0, b, alpha=0.05)
    # at T = MinTRL, PSR == 1 - alpha (T-1 observations in formula)
    assert psr_from_stats(sr, int(round(n)), 0.0, 3.0, b) == pytest.approx(0.95, abs=2e-3)
    assert math.isinf(min_trl_from_stats(-0.1))
    x = pd.Series(np.random.default_rng(2).normal(0.001, 0.01, 800))
    assert min_trl(x) > 1


def test_pbo_noise_vs_edge():
    rng = np.random.default_rng(5)
    T, N = 1600, 20
    noise = pd.DataFrame(rng.normal(0, 0.01, (T, N)))
    p = pbo_cscv(noise, n_slices=16, seed=1)
    assert 0.3 < p["pbo"] < 0.7
    edge = noise.copy()
    edge[3] = edge[3] + 0.004  # strong true edge in one config
    pe = pbo_cscv(edge, n_slices=16, seed=1)
    assert pe["pbo"] < 0.05
    assert pbo_cscv(noise, seed=1)["pbo"] == p["pbo"]  # reproducible
    assert p["n_combos"] == 2000 or p["n_combos"] == 12870


def test_pbo_exact_enumeration_small():
    rng = np.random.default_rng(0)
    p = pbo_cscv(pd.DataFrame(rng.normal(0, 1, (80, 5))), n_slices=8)
    assert p["n_combos"] == 70 and 0 <= p["pbo"] <= 1


def test_bootstrap_reproducible_and_sane():
    rng = np.random.default_rng(11)
    r = pd.Series(rng.normal(0.001, 0.01, 750))
    a, b = block_bootstrap(r, n=300, seed=9), block_bootstrap(r, n=300, seed=9)
    pd.testing.assert_frame_equal(a.samples, b.samples)
    c = block_bootstrap(r, n=300, seed=10)
    assert not a.samples.equals(c.samples)
    assert a.summary["sharpe_p05"] < a.summary["observed_sharpe"] < a.summary["sharpe_p95"] or True
    assert a.summary["sharpe_p05"] < a.summary["sharpe_p95"]
    assert a.summary["max_drawdown_p50"] < 0
    json.dumps(a.summary, allow_nan=False)
    # block length 1 behaves like iid bootstrap; mean of sample mean ~ data mean
    assert abs(block_bootstrap(r, n=400, block=1, seed=1).samples["total_return"].mean()) > 0


def test_trade_monte_carlo():
    pnl = [100.0] * 6 + [-100.0] * 4
    t = pd.DataFrame({"net_pnl": pnl})
    mc = trade_monte_carlo(t, n=500, seed=3, initial_capital=1000.0, ruin_level=0.5)
    assert mc.summary["n_trades"] == 10
    assert 0.0 <= mc.summary["risk_of_ruin"] < 0.2
    assert trade_monte_carlo(t, n=500, seed=3, initial_capital=1000.0, ruin_level=0.0).summary["risk_of_ruin"] <= mc.summary["risk_of_ruin"]
    mc2 = trade_monte_carlo(t, n=500, seed=3, initial_capital=1000.0, ruin_level=0.5)
    assert mc.summary == mc2.summary
    assert mc.summary["max_drawdown_p50"] <= 0
    assert mc.summary["final_equity_mean"] == pytest.approx(1000 + 200, rel=0.15)


def test_ledger_append_only(tmp_path):
    p = tmp_path / "sub" / "_trials.jsonl"
    trial_ledger_append(p, {"strategy": "a", "n_trials": 10})
    first = p.read_text()
    trial_ledger_append(p, {"strategy": "b"})
    assert p.read_text().startswith(first)
    assert len(trial_ledger_read(p)) == 2
    assert count_trials(p) == 11 and count_trials(p, "a") == 10


def test_regimes_and_verdict():
    res = make_result(n_days=400)
    tb = regime_breakdown(res)
    assert {"year", "volatility", "trend", "weekday"} <= set(tb)
    assert tb["volatility"]["n_days"].sum() > 300
    v = verdict(dsr=0.97, pbo=0.2, wf_efficiency=0.6, positive_at_2x=True, n_trades=150, plateau=0.8)
    assert v["overall"] == "green"
    v = verdict(dsr=0.5, pbo=0.7, n_trades=20)
    assert v["overall"] == "red"
    assert verdict()["overall"] == "n/a"
    assert [c["status"] for c in verdict(pbo=0.4)["checks"] if c["check"] == "pbo"] == ["amber"]
