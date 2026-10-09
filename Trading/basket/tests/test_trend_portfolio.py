import numpy as np
import pytest

from mrscore.backtest.trend_portfolio import month_end_mask, performance, run_trend_portfolio, trend_signals
from mrscore.config.models import TrendPortfolioParams, TrendPortfolioRootConfig


def business_days(n, start="2020-01-01"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + 3 * n)
    d = d[np.is_busday(d)]
    return d[:n]


def params(**kw):
    base = dict(sma_months=3, risk_off="BOND", cash_rate=None, execution_lag_bars=1, costs_bps=0.0,
                leverage=1.0, financing_spread_bps=0.0, initial_cash=100.0)
    base.update(kw)
    return TrendPortfolioParams(**base)


def test_month_end_mask_marks_last_bar_of_each_month():
    d = np.array(["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28", "2020-03-02"], dtype="datetime64[D]")
    assert month_end_mask(d).tolist() == [False, True, False, True, True]


def test_uptrending_assets_stay_invested_like_equal_weight_buy_and_hold():
    dates = business_days(300)
    t = np.arange(300)
    prices = np.column_stack([100 * 1.001 ** t, 50 * 1.0005 ** t])
    res = run_trend_portfolio(prices=prices, risk_off=np.full(300, 10.0), dates=dates, params=params())
    assert all(s.on.all() for s in res.signals)
    assert res.weights[-1, -1] == 0.0
    # invested from bar 1 onward with monthly rebalancing to 50/50: grows between the two assets
    total = res.equity[-1] / res.equity[0] - 1
    assert prices[-1, 1] / prices[1, 1] - 1 < total < prices[-1, 0] / prices[1, 0] - 1


def test_asset_below_its_sma_moves_to_risk_off_after_the_lag():
    dates = business_days(200)
    t = np.arange(200)
    falling = 100 * 0.995 ** t
    rising = 100 * 1.001 ** t
    res = run_trend_portfolio(prices=np.column_stack([rising, falling]), risk_off=np.full(200, 10.0),
                              dates=dates, params=params())
    flip = next(s for s in res.signals if not s.on[1])  # first month-end below its SMA
    assert flip.on.tolist() == [True, False]
    assert flip.weights.tolist() == [0.5, 0.0, 0.5]
    assert res.weights[flip.index + 1].tolist() == [0.5, 0.0, 0.5]
    assert res.weights[flip.index, 1] > 0  # still held on the signal bar itself


def test_signals_default_to_on_until_enough_month_ends():
    dates = business_days(60)
    prices = np.column_stack([np.linspace(100, 50, 60)])
    sig = trend_signals(prices, month_end_mask(dates), sma_months=12)
    assert all(s.on.all() for s in sig)


def test_costs_and_leverage():
    dates = business_days(250)
    t = np.arange(250)
    prices = np.column_stack([100 * 1.001 ** t, 100 * (1 + 0.05 * np.sin(t / 7))])
    risk_off = np.full(250, 10.0)
    free = run_trend_portfolio(prices=prices, risk_off=risk_off, dates=dates, params=params())
    paid = run_trend_portfolio(prices=prices, risk_off=risk_off, dates=dates, params=params(costs_bps=10.0))
    assert paid.equity[-1] < free.equity[-1]
    assert np.all(paid.costs >= 0) and paid.costs.sum() > 0

    lev = run_trend_portfolio(prices=prices, risk_off=risk_off, dates=dates, params=params(), leverage=2.0)
    r1 = free.equity[1:] / free.equity[:-1] - 1
    r2 = lev.equity[1:] / lev.equity[:-1] - 1
    np.testing.assert_allclose(r2, 2 * r1, atol=1e-12)  # zero financing cost


def test_performance_of_a_steady_curve():
    dates = business_days(253)
    eq = 100 * 1.0004 ** np.arange(253)
    p = performance(eq, dates)
    assert p["max_dd"] == 0.0
    assert p["cagr"] > 0 and p["vol"] < 1e-9


def test_config_rejects_risk_off_inside_universe():
    with pytest.raises(ValueError):
        TrendPortfolioRootConfig.model_validate({
            "config_version": 1,
            "data": {"price_field": "close", "returns_mode": "log", "min_bars_required": 1,
                     "tickers": ["A", "B"], "period": "5y", "interval": "1d"},
            "trend_portfolio": {"risk_off": "A"},
        })
