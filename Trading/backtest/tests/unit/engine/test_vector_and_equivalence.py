import time

import numpy as np
import pandas as pd
import pytest
from helpers import daily_panel, ex

from tradelab.config import DataCfg
from tradelab.data import load_panel
from tradelab.engine import run_event, run_vector
from tradelab.strategy import Order, Strategy

CAP = 100_000.0


class Fixed(Strategy):
    name = "_fixed"
    mode = "vector"

    def __init__(self, w, params=None):
        super().__init__(params)
        self.w = w

    def signals(self, data):
        return pd.DataFrame({data.primary: self.w}, index=data.index)


O = [100, 102, 104, 101, 103]
C = [100, 103, 102, 105, 104]


def test_next_open_decomposition_weight_mode():
    p = daily_panel(O, C)
    r = run_vector(p, Fixed([1, 0, 0, 0, 0]), ex(fill="next_open"), CAP)
    # eff = [0,1,0,0,0] : bought at open1 (102), sold at open2 (104)
    e1 = CAP * (C[1] / O[1])                       # leg2 on day1 : 103/102
    e2 = e1 * (O[2] / C[1])                        # leg1 on day2 : 104/103 (overnight/gap leg)
    assert r.equity.iloc[0] == CAP and r.equity.iloc[1] == pytest.approx(e1)
    assert r.equity.iloc[2] == pytest.approx(e2) and r.equity.iloc[4] == pytest.approx(e2)
    # fill decomposition: P&L = open2/open1 - 1
    assert e2 / CAP == pytest.approx(104 / 102)
    t = r.trades.iloc[0]
    assert t.entry_px == 102 and t.exit_px == 104 and t.side == "long"


def test_next_close_and_unsafe_fill():
    p = daily_panel(O, C)
    r = run_vector(p, Fixed([1, 0, 0, 0, 0]), ex(fill="next_close"), CAP)
    # eff=[0,1,0,0,0] bought at close1 (103), sold at close2 (102)
    assert r.equity.iloc[2] == pytest.approx(CAP * 102 / 103)
    with pytest.raises(ValueError):
        run_vector(p, Fixed([1, 0, 0, 0, 0]), ex(fill="same_close_unsafe"), CAP)
    r = run_vector(p, Fixed([1, 0, 0, 0, 0]), ex(fill="same_close_unsafe", allow_unsafe=True), CAP)
    assert r.equity.iloc[0] == CAP                        # bought at close0
    assert r.equity.iloc[1] == pytest.approx(CAP * 103 / 100)


def test_costs_in_bps_weight_mode():
    p = daily_panel(O, C)
    r = run_vector(p, Fixed([1, 0, 0, 0, 0]), ex(fill="next_open", commission_bps=10, slippage_bps=10), CAP)
    c = 20 / 1e4
    e1 = CAP * (1 - c) * (C[1] / O[1])
    e2 = e1 * (O[2] / C[1]) * (1 - c)
    assert r.equity.iloc[2] == pytest.approx(e2)
    assert r.costs_daily.sum() == pytest.approx(CAP * c + (e1 * O[2] / C[1]) * c)


def test_cash_accrual_flat_and_partial():
    p = daily_panel(O, C, cash=0.001)
    r = run_vector(p, Fixed([0, 0, 0, 0, 0]), ex(), CAP)
    assert r.equity.iloc[-1] == pytest.approx(CAP * 1.001 ** 5)
    # 50% weight: cash leg earns on the other 50%
    r = run_vector(p, Fixed([0.5] * 5), ex(), CAP)
    legs = []
    prev_eff = 0.0
    e = CAP
    for k in range(5):
        eff = 0.5 if k >= 1 else 0.0
        r1 = 0.0 if k == 0 else prev_eff * (O[k] / C[k - 1] - 1)
        e = e * (1 + r1) * (1 + eff * (C[k] / O[k] - 1)) * (1 + (1 - eff) * 0.001)
        prev_eff = eff
    assert r.equity.iloc[-1] == pytest.approx(e)


def test_borrow_and_leverage_cap():
    p = daily_panel(O, C)
    r = run_vector(p, Fixed([3.0] * 5), ex(leverage_cap=1.5), CAP)
    assert np.abs(r.positions.iloc[:, 0]).max() == pytest.approx(1.5)


def test_units_mode_with_per_contract_costs_mnq():
    # MNQ daily panel (tick .25, $2/pt): hold 2 contracts from open1 to open3
    p = daily_panel([100, 102, 104, 101, 103], [100, 103, 102, 105, 104], symbol="MNQ")
    r = run_vector(p, Fixed([2, 2, 0, 0, 0]), ex(vector_sizing="units", commission_per_contract=1.0, slippage_ticks=1), CAP)
    pnl = 2 * 2 * (101 - 102)                              # (open3 - open1) * qty * pv = -4 ... held through open3? eff=[0,2,2,0,0]
    cost_per_side = 2 * (1.0 + 0.25 * 2)                   # qty * (fee + 1 tick*pv)
    assert r.equity.iloc[-1] == pytest.approx(CAP + pnl - 2 * cost_per_side)
    assert r.trades.iloc[0].gross_pnl == pytest.approx(pnl)
    assert r.costs_daily.sum() == pytest.approx(2 * cost_per_side)


class FlipStrategy(Strategy):
    """vector + event twin: target = sign of 3-bar momentum (units: +/-1)."""
    name = "_flip"
    mode = "vector"

    @staticmethod
    def target(close):
        return np.sign(close.pct_change(3)).fillna(0.0)

    def signals(self, data):
        return self.target(data.field("close"))


class FlipEvent(Strategy):
    name = "_flip_event"
    mode = "event"

    def prepare(self, data):
        return {"target": FlipStrategy.target(data[data.primary]["close"])}

    def on_bar(self, ctx):
        tgt, cur = ctx.f("target"), ctx.position
        if tgt == np.sign(cur):
            return None
        out = []
        if cur != 0:
            out.append(Order.flatten())
        if tgt != 0:
            out.append(Order("buy" if tgt > 0 else "sell", qty=1))
        return out


def test_vector_vs_event_equivalence_daily():
    p = load_panel(DataCfg(source="synthetic", symbols=["SPY"], freq="1d", start="2018-01-01", end="2021-12-31"))
    cfg = dict(commission_per_contract=0.0)
    rv = run_vector(p, FlipStrategy(), ex(vector_sizing="units", **cfg), CAP)
    re_ = run_event(p, FlipEvent(), ex(**cfg), CAP)
    np.testing.assert_allclose(rv.equity.to_numpy(), re_.equity.to_numpy(), rtol=0, atol=1e-6)
    np.testing.assert_allclose(rv.returns_daily.to_numpy(), re_.returns_daily.to_numpy(), atol=1e-12)
    assert len(re_.trades) > 20
    assert re_.trades.net_pnl.sum() == pytest.approx(rv.equity.iloc[-1] - CAP)


def test_vector_engine_20y_daily_under_50ms():
    p = load_panel(DataCfg(source="synthetic", symbols=["SPY"], freq="1d", start="2005-01-03", end="2024-12-31"))
    assert len(p.index) > 4900
    from tradelab.strategy.registry import get_strategy
    cls = get_strategy("sma_cross")
    strat = cls(cls.Params())
    sig = strat.signals(p).to_numpy()
    best = 1e9
    for _ in range(7):
        t0 = time.perf_counter()
        run_vector(p, strat, ex(commission_bps=1, slippage_bps=1), CAP, signals=sig)
        best = min(best, time.perf_counter() - t0)
    assert best < 0.05, f"vector run took {best*1000:.1f} ms"
