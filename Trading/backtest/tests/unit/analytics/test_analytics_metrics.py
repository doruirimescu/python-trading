import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "golden"))
from synth import TRADE_COLS, make_result, result_from_returns  # noqa: E402

from tradelab.analytics import (compute_metrics, drawdown_stats, periodic_tables, prob_run_at_least,  # noqa: E402
                                r_multiple_stats, trade_stats)


def _r(vals):
    return pd.Series(vals, index=pd.bdate_range("2024-01-01", periods=len(vals)), dtype=float)


def test_hand_computed_basic():
    r = _r([0.10, -0.05, 0.02, -0.10, 0.04])
    m = compute_metrics(result_from_returns(r), periods_per_year=252)
    total = 1.10 * 0.95 * 1.02 * 0.90 * 1.04 - 1
    assert m["total_return"] == pytest.approx(total)
    assert m["sharpe"] == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(252))
    dd = min(0.95 - 1, 1.10 * .95 * 1.02 * 0.9 / (1.10 * 1.02 * .95 / .95 * 1) - 1)
    curve = np.cumprod(1 + r.to_numpy())
    peak = np.maximum.accumulate(np.r_[1.0, curve])[1:]
    assert m["max_drawdown"] == pytest.approx((curve / peak - 1).min())
    assert m["cagr"] == pytest.approx((1 + total) ** (365.25 / 5) - 1)       # calendar span: 5 days (Mon-Fri)
    dsd = math.sqrt(np.mean(np.minimum(r.to_numpy(), 0) ** 2))
    assert m["sortino"] == pytest.approx(r.mean() / dsd * math.sqrt(252))
    assert m["best_day"] == 0.10 and m["worst_day"] == -0.10
    assert m["hit_rate_days"] == pytest.approx(3 / 5)
    assert m["calmar"] == pytest.approx(m["cagr"] / abs(m["max_drawdown"]))
    assert m["var_95_hist"] == pytest.approx(-np.quantile(r, 0.05))
    assert dd is not None


def test_drawdown_recovery_and_duration():
    r = _r([0.1, -0.1, -0.1, 0.1, 0.1, 0.2, -0.05])
    s = drawdown_stats(r)
    assert s["max_dd_recovered"] is True
    assert s["max_drawdown"] == pytest.approx(0.9 * 0.9 - 1)
    assert s["max_dd_duration_sessions"] == 4  # days 2..5 underwater (index1..4)
    unrec = drawdown_stats(_r([0.1, -0.2, 0.01]))
    assert unrec["max_dd_recovered"] is False and unrec["time_to_recovery_days"] is None


def test_json_serialisable_and_sections():
    import json
    m = compute_metrics(make_result())
    json.dumps(m, allow_nan=False)
    for k in ("sharpe", "trades", "rmultiple", "benchmark", "var_95_cf", "ulcer_index", "exposure"):
        assert k in m
    assert m["benchmark"]["beta"] is not None
    assert m["trades"]["n_trades"] == 60


def test_trade_stats_hand():
    t = pd.DataFrame({"net_pnl": [100.0, -50.0, -50.0, 200.0, -25.0],
                      "exit_ts": pd.date_range("2024-01-01", periods=5, tz="UTC")})
    s = trade_stats(t, n_days=10)
    assert s["hit_rate"] == pytest.approx(0.4)
    assert s["profit_factor"] == pytest.approx(300 / 125)
    assert s["payoff_ratio"] == pytest.approx(150 / (125 / 3))
    assert s["expectancy"] == pytest.approx(35.0)
    assert s["max_consecutive_losses"] == 2
    assert s["trades_per_day"] == pytest.approx(0.5)


def test_rmultiple_sqn_and_streak_prob():
    R = [1.0, -1.0, 2.0, -1.0, 0.5, -1.0, -1.0, 1.5]
    t = pd.DataFrame({"R_net": R, "R_gross": R, "exit_ts": pd.date_range("2024-01-01", periods=8, tz="UTC")})
    s = r_multiple_stats(t)
    a = np.array(R)
    assert s["expectancy_r"] == pytest.approx(a.mean())
    assert s["sqn"] == pytest.approx(math.sqrt(8) * a.mean() / a.std(ddof=1))
    assert s["max_consecutive_losses"] == 2
    # exact streak probability: 2 trials, p=.5, run>=2 -> .25 ; 3 trials -> .375
    assert prob_run_at_least(2, 0.5, 2) == pytest.approx(0.25)
    assert prob_run_at_least(3, 0.5, 2) == pytest.approx(0.375)
    assert prob_run_at_least(5, 0.3, 1) == pytest.approx(1 - 0.7**5)


def test_empty_trades_ok():
    m = compute_metrics(make_result(with_trades=False, with_bench=False))
    assert m["trades"]["n_trades"] == 0 and m["benchmark"] == {}


def test_periodic_tables():
    res = make_result()
    tb = periodic_tables(res)
    for k in ("year", "month", "weekday", "by_exit_reason", "by_entry_hour"):
        assert k in tb
    y = tb["year"]
    r = res.returns_daily
    assert y.loc[2022, "return"] == pytest.approx((1 + r[r.index.year == 2022]).prod() - 1)
    assert tb["month"].shape[1] == 12
    assert tb["by_entry_hour"].index.tolist() == [14]
    assert list(res.trades.columns) == TRADE_COLS
