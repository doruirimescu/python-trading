"""Vectorised engine: strategy emits a target position per bar (weights or units) decided at that bar's close.

The ENGINE owns all shifting.  With eff_k the position in force after the fill on bar k and P_k the fill price:
    next_open        eff_k = W[k-1],  P_k = open_k
    next_close       eff_k = W[k-1],  P_k = close_k
    same_close_unsafe eff_k = W[k],   P_k = close_k   (look-ahead; needs allow_unsafe)
  leg1_k = eff_{k-1} * (P_k / close_{k-1} - 1)      (held position up to the fill)
  leg2_k = eff_k     * (close_k / P_k - 1)          (new position after the fill)
Weight mode:  E_k = E_{k-1} (1+leg1) (1 - cost) (1+leg2) (1 + cash - borrow)
Units mode:   pnl_k = pv (eff_{k-1}(P_k-close_{k-1}) + eff_k (close_k-P_k)) - cost$ ; E_k = E_{k-1} + pnl_k + cash
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config.schema import ExecCfg
from ..data.panel import Panel
from ..strategy.base import Strategy
from .costs import CostModel
from .result import TRADE_COLUMNS, RunResult, daily_from_equity, daily_sum, empty_trades


def _signals(panel: Panel, strategy: Strategy) -> np.ndarray:
    sig = strategy.signals(panel)
    if isinstance(sig, pd.Series):
        sig = sig.to_frame(panel.primary)
    sig = sig.reindex(index=panel.index, columns=panel.symbols)
    return sig.fillna(0.0).to_numpy(float)


def run_vector(panel: Panel, strategy: Strategy, ex: ExecCfg, capital: float, *, cost_mult: float = 1.0,
               meta: dict | None = None, signals: np.ndarray | None = None) -> RunResult:
    if ex.fill == "same_close_unsafe" and not ex.allow_unsafe:
        raise ValueError("fill=same_close_unsafe requires execution.allow_unsafe: true (look-ahead!)")
    syms = panel.symbols
    idx = panel.index
    T, M = len(idx), len(syms)
    W = _signals(panel, strategy) if signals is None else signals
    units = ex.vector_sizing == "units"
    if ex.leverage_cap and not units:
        gross = np.abs(W).sum(axis=1)
        scale = np.where(gross > ex.leverage_cap, ex.leverage_cap / np.maximum(gross, 1e-12), 1.0)
        W = W * scale[:, None]
    O = panel.field("open").to_numpy(float)
    C = panel.field("close").to_numpy(float)
    pvs = np.array([panel.specs[s].point_value for s in syms])
    cms = [CostModel.from_cfg(ex, panel.specs[s], cost_mult) for s in syms]
    fee = np.array([c.fee_per_side for c in cms])
    bps = np.array([(c.commission_bps + c.slip_bps) / 1e4 for c in cms])
    slip_pts = np.array([c.slip_ticks * c.tick for c in cms])

    if ex.fill == "same_close_unsafe":
        eff = W
        P = C
    else:
        eff = np.vstack([np.zeros((1, M)), W[:-1]])
        P = O if ex.fill == "next_open" else C
    eff_prev = np.vstack([np.zeros((1, M)), eff[:-1]])
    Cprev = np.vstack([C[:1], C[:-1]])
    r1 = P / Cprev - 1.0
    r1[0] = 0.0
    r2 = C / P - 1.0
    turn = np.abs(eff - eff_prev)
    rate = bps[None, :] + slip_pts[None, :] / P + fee[None, :] / (P * pvs[None, :])   # fraction of notional per unit weight

    sd = panel.session_dates().to_numpy()
    sdi = pd.DatetimeIndex(sd)
    cnt = pd.Series(1, index=sdi).groupby(level=0).transform("size").to_numpy()
    day_frac = 1.0 / cnt
    rf_bar = np.zeros(T)
    if panel.cash is not None:
        rf_bar = panel.cash.reindex(sdi).fillna(0.0).to_numpy() * day_frac
    spread = ex.cash_spread_bps / 1e4 / 252 * day_frac
    borrow = ex.borrow_bps * cost_mult / 1e4 / 252 * day_frac   # cost_mult scales borrow too

    if not units:
        leg1 = (eff_prev * r1).sum(axis=1)
        cost_f = (turn * rate).sum(axis=1)
        cash_w = 1.0 - eff.sum(axis=1)
        short_w = np.maximum(-eff, 0).sum(axis=1)
        carry = cash_w * rf_bar - np.maximum(-cash_w, 0) * spread - short_w * borrow
        leg2 = (eff * r2).sum(axis=1)
        fac = (1 + leg1) * (1 - cost_f) * (1 + leg2) * (1 + carry)
        eq = capital * np.cumprod(fac)
        e_prev = np.r_[capital, eq[:-1]]
        cost_usd = e_prev * (1 + leg1) * cost_f + e_prev * short_w * borrow
    else:
        pnl = ((eff_prev * (P - Cprev) * pvs).sum(axis=1)) + (eff * (C - P) * pvs).sum(axis=1)
        pnl[0] = (eff[0] * (C[0] - P[0]) * pvs).sum()
        cost_usd = (turn * rate * P * pvs).sum(axis=1)
        if np.any(rf_bar != 0):
            eq = np.empty(T)
            e = capital
            for k in range(T):
                e = e + pnl[k] - cost_usd[k] + e * rf_bar[k]
                eq[k] = e
        else:
            eq = capital + np.cumsum(pnl - cost_usd)

    eq_s = pd.Series(eq, index=idx, name="equity")
    rets = daily_from_equity(eq_s, sdi, capital)
    costs_d = daily_sum(cost_usd, sdi)
    trades = _derive_trades(panel, syms, idx, eff, P, C, pvs, rate, eq, capital, units, sd, T)
    m = dict(meta or {})
    m.update({"mode": "vector", "freq": panel.freq, "fill": ex.fill, "sizing": ex.vector_sizing, "cost_mult": cost_mult})
    return RunResult(
        equity=eq_s, returns_daily=rets, positions=pd.DataFrame(eff, index=idx, columns=syms), trades=trades,
        costs_daily=costs_d, benchmark_daily=panel.benchmark, rf_daily=panel.cash,
        initial_capital=float(capital), meta=m,
    )


def _derive_trades(panel, syms, idx, eff, P, C, pvs, rate, eq, capital, units, sd, T) -> pd.DataFrame:
    """Round trips from position segments (approximate: sizing changes inside a segment are ignored)."""
    rows = []
    e_prev = np.r_[capital, eq[:-1]]
    for s_i, sym in enumerate(syms):
        q = eff[:, s_i]
        sgn = np.sign(q)
        chg = np.flatnonzero(np.r_[sgn[0] != 0, sgn[1:] != sgn[:-1]])
        starts = [k for k in chg if sgn[k] != 0]
        for k in starts:
            nxt = chg[chg > k]
            m = int(nxt[0]) if len(nxt) else T - 1
            end_at_close = not len(nxt)
            exit_px = C[m, s_i] if end_at_close else P[m, s_i]
            ep = P[k, s_i]
            d = sgn[k]
            qty = abs(q[k]) if units else abs(q[k]) * e_prev[k] / (ep * pvs[s_i])
            gross = d * qty * (exit_px - ep) * pvs[s_i]
            costs = qty * pvs[s_i] * (rate[k, s_i] * ep + (0.0 if end_at_close else rate[m, s_i] * exit_px))
            rows.append({
                "id": len(rows) + 1, "symbol": sym, "side": "long" if d > 0 else "short", "qty": qty,
                "entry_ts": idx[k], "entry_px": ep, "exit_ts": idx[m], "exit_px": exit_px,
                "exit_reason": "end_of_data" if end_at_close else "signal", "initial_stop": np.nan,
                "target": np.nan, "R_gross": np.nan, "R_net": np.nan, "MAE_R": np.nan, "MFE_R": np.nan,
                "MAE_usd": np.nan, "MFE_usd": np.nan, "bars_held": m - k, "session_date": sd[k], "tag": "",
                "gross_pnl": gross, "costs": costs, "net_pnl": gross - costs, "commission": np.nan,
                "slippage_cost": np.nan,
            })
    if not rows:
        return empty_trades()
    return pd.DataFrame(rows, columns=TRADE_COLUMNS).sort_values("entry_ts").reset_index(drop=True)
