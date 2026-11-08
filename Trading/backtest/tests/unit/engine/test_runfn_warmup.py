"""make_run_fn: warm-up correctness, cost_mult scaling, picklability."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from tradelab.config.schema import RunConfig
from tradelab.engine.runner import make_run_fn, warmup_sessions_for
from tradelab.robustness import run_grid

HERE = Path(__file__).resolve()
STRAT = str(HERE.parents[2] / "prior_day_brk.py")


def _intraday_cfg(**exec_kw):
    return RunConfig.model_validate({
        "data": {"source": "synthetic", "symbols": ["MNQ"], "start": "2023-03-01", "end": "2023-04-28", "freq": "5m",
                 "base_freq": "1m", "options": {"seed": 3}},
        "strategy": {"name": "prior_day_brk", "path": STRAT, "warmup_sessions": 5},
        "execution": {"slippage_ticks": 1, "flatten_at": "15:55", **exec_kw}, "initial_capital": 50000, "seed": 1})


def test_window_equals_slice_of_full_run():
    cfg = _intraday_cfg()
    fn = make_run_fn(cfg)
    full = fn({})
    sd = pd.DatetimeIndex(sorted(full.returns_daily.index))
    start, end = sd[12], sd[30]
    win = fn({}, start=start, end=end)
    ft = full.trades[(full.trades.session_date >= start) & (full.trades.session_date <= end)].reset_index(drop=True)
    wt = win.trades.reset_index(drop=True)
    assert len(ft) > 3, "test strategy must trade"
    cols = ["entry_ts", "entry_px", "exit_ts", "exit_px", "side", "qty", "exit_reason", "net_pnl", "costs"]
    pd.testing.assert_frame_equal(wt[cols], ft[cols], check_dtype=False)
    eq_w = win.returns_daily.index
    assert eq_w.min() >= start and eq_w.max() <= end
    # trades + dates inside window only
    assert win.trades.session_date.min() >= start and win.trades.session_date.max() <= end
    assert abs(win.trades.net_pnl.sum() - ft.net_pnl.sum()) < 1e-6


def test_without_warmup_first_session_untradable_but_with_warmup_trades_on_day_one():
    cfg = _intraday_cfg()
    fn = make_run_fn(cfg)
    full = fn({})
    d = pd.DatetimeIndex(sorted(full.returns_daily.index))[8]
    first_day_trades = full.trades[full.trades.session_date == d]
    win = fn({}, start=d, end=d + pd.Timedelta(days=10))
    assert len(win.trades[win.trades.session_date == d]) == len(first_day_trades)


def test_cost_mult_scales_all_costs():
    for ex in ({"commission_bps": 0.0}, {"commission_per_contract": 1.5}):
        cfg = _intraday_cfg(**ex)
        fn = make_run_fn(cfg)
        c0 = fn({}, cost_mult=0.0).costs_daily.sum()
        c1 = fn({}, cost_mult=1.0).costs_daily.sum()
        c2 = fn({}, cost_mult=2.0).costs_daily.sum()
        assert c0 == 0 and c1 > 0
        assert abs(c2 - 2 * c1) < 1e-6 * max(1, c1)
    dcfg = RunConfig.model_validate({
        "data": {"source": "synthetic", "symbols": ["SPY"], "start": "2018-01-02", "end": "2020-12-31", "freq": "1d"},
        "strategy": {"name": "sma_cross", "params": {"fast": 10, "slow": 50, "long_only": False}},
        "execution": {"commission_bps": 2, "slippage_bps": 3, "borrow_bps": 50}, "initial_capital": 100000})
    f = make_run_fn(dcfg)
    r0, r1, r2 = (f({}, cost_mult=m) for m in (0, 1, 2))
    assert r0.costs_daily.sum() == 0
    # weight-mode costs are a fraction of (cost-dependent) equity: exact on the first costly day, ordered afterwards
    d = r1.costs_daily[r1.costs_daily > 0].index[0]
    assert abs(r2.costs_daily[d] - 2 * r1.costs_daily[d]) < 1e-9 * r1.costs_daily[d]
    assert r2.costs_daily.sum() > 1.6 * r1.costs_daily.sum() > 0


def test_run_fn_picklable_and_parallel_grid():
    dcfg = RunConfig.model_validate({
        "data": {"source": "synthetic", "symbols": ["SPY"], "start": "2018-01-02", "end": "2020-12-31", "freq": "1d"},
        "strategy": {"name": "sma_cross"}, "execution": {"commission_bps": 1}, "initial_capital": 100000})
    fn = make_run_fn(dcfg, reload_in_worker=True)
    fn2 = pickle.loads(pickle.dumps(fn))
    a = fn({"fast": 10}).returns_daily
    b = fn2({"fast": 10}).returns_daily
    pd.testing.assert_series_equal(a, b)
    grid = {"fast": [5, 10, 20], "slow": [60, 100]}
    g1 = run_grid(fn, grid, n_jobs=1)
    g2 = run_grid(fn, grid, n_jobs=2)
    assert np.allclose(g1.table["objective"].fillna(0), g2.table["objective"].fillna(0))


def test_warmup_default_by_frequency():
    assert warmup_sessions_for(RunConfig.model_validate({"data": {"symbols": ["X"], "freq": "1d"}, "strategy": {"name": "a"}})) == 300
    assert warmup_sessions_for(RunConfig.model_validate({"data": {"symbols": ["X"], "freq": "5m"}, "strategy": {"name": "a"}})) == 20
