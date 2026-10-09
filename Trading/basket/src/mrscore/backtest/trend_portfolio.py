"""Trend-filtered equal-weight portfolio (time-series momentum overlay).

Rules, evaluated at every month-end close:
  - each of the N assets is "on" when its close is above the simple average of its
    last `sma_months` month-end closes (on by default until that much history exists)
  - target weight: 1/N for every "on" asset; the "off" slices go to the risk-off asset
  - targets are executed `execution_lag_bars` closes later; costs are paid on the
    traded notional; between rebalances the weights drift with prices

Leverage L is applied to the daily (net-of-cost) portfolio return, financing the
borrowed (L - 1) at the cash rate plus a spread.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from mrscore.config.models import TrendPortfolioParams


@dataclass(frozen=True)
class TrendSignal:
    index: int            # month-end bar the signal was computed on
    on: np.ndarray        # (N,) bool, asset above its SMA
    weights: np.ndarray   # (N + 1,) target weights, last = risk-off


@dataclass(frozen=True)
class TrendPortfolioResult:
    equity: np.ndarray        # (T,) portfolio value
    weights: np.ndarray       # (T, N + 1) end-of-bar weights, last column = risk-off
    signals: list[TrendSignal]
    turnover: np.ndarray      # (T,) traded notional / equity on rebalance bars
    costs: np.ndarray         # (T,) cost paid, as a fraction of equity


def month_end_mask(dates: np.ndarray) -> np.ndarray:
    """True on the last bar of each calendar month present in `dates`."""
    months = np.asarray(dates).astype("datetime64[M]")
    mask = np.ones(len(months), dtype=bool)
    mask[:-1] = months[1:] != months[:-1]
    return mask


def daily_cash_rate(cash_rate_pct: Optional[np.ndarray], T: int) -> np.ndarray:
    """Per-bar cash return from an annualized percent yield, known at the previous close."""
    if cash_rate_pct is None:
        return np.zeros(T)
    y = np.asarray(cash_rate_pct, dtype=np.float64) / 100.0 / 252.0
    out = np.zeros(T)
    out[1:] = y[:-1]
    return np.nan_to_num(out)


def trend_signals(prices: np.ndarray, month_end: np.ndarray, sma_months: int) -> list[TrendSignal]:
    T, N = prices.shape
    me_idx = np.flatnonzero(month_end)
    signals = []
    for k, i in enumerate(me_idx):
        window = me_idx[max(0, k - sma_months + 1): k + 1]
        if len(window) < sma_months:
            on = np.ones(N, dtype=bool)
        else:
            on = prices[i] > prices[window].mean(axis=0)
        w = np.zeros(N + 1)
        w[:N] = on / N
        w[N] = (~on).sum() / N
        signals.append(TrendSignal(index=int(i), on=on, weights=w))
    return signals


def run_trend_portfolio(
    *,
    prices: np.ndarray,
    risk_off: np.ndarray,
    dates: np.ndarray,
    params: TrendPortfolioParams,
    cash_rate_pct: Optional[np.ndarray] = None,
    leverage: Optional[float] = None,
    sma_months: Optional[int] = None,
) -> TrendPortfolioResult:
    """
    prices: (T, N) closes of the portfolio assets (total-return adjusted)
    risk_off: (T,) closes of the risk-off asset
    cash_rate_pct: (T,) annualized cash yield in percent, or None for 0%
    leverage / sma_months override the values in `params` (for sweeps).
    """
    prices = np.asarray(prices, dtype=np.float64)
    T, N = prices.shape
    L = float(params.leverage if leverage is None else leverage)
    sma = int(params.sma_months if sma_months is None else sma_months)

    assets = np.column_stack([prices, np.asarray(risk_off, dtype=np.float64)])
    rets = np.zeros_like(assets)
    rets[1:] = assets[1:] / assets[:-1] - 1.0
    cash = daily_cash_rate(cash_rate_pct, T)
    financing = cash + params.financing_spread_bps / 1e4 / 252.0
    cost_rate = params.costs_bps / 1e4

    signals = trend_signals(prices, month_end_mask(dates), sma)
    pending = {s.index + params.execution_lag_bars: s.weights for s in signals}

    equity = np.empty(T)
    weights = np.zeros((T, N + 1))
    turnover = np.zeros(T)
    costs = np.zeros(T)
    w = np.zeros(N + 1)  # in cash (0%) until the first rebalance executes
    v = float(params.initial_cash)
    for t in range(T):
        r = 0.0
        if t:
            r = float(rets[t] @ w)
            grown = w * (1.0 + rets[t])
            s = grown.sum()
            w = grown / s if s > 0 else grown
        target = pending.get(t)
        if target is not None:
            turnover[t] = np.abs(target - w).sum()
            costs[t] = cost_rate * turnover[t]
            r = (1.0 + r) * (1.0 - costs[t]) - 1.0
            w = target.copy()
        v *= 1.0 + L * r - (L - 1.0) * financing[t]
        equity[t] = v
        weights[t] = w
    return TrendPortfolioResult(equity=equity, weights=weights, signals=signals, turnover=turnover, costs=costs)


def performance(equity: np.ndarray, dates: np.ndarray, cash_rate_pct: Optional[np.ndarray] = None) -> dict:
    """CAGR, volatility, Sharpe (over cash), max drawdown and Calmar of an equity curve."""
    e = np.asarray(equity, dtype=np.float64)
    d = np.asarray(dates).astype("datetime64[D]")
    years = (d[-1] - d[0]).astype(int) / 365.25
    r = e[1:] / e[:-1] - 1.0
    ex = r - daily_cash_rate(cash_rate_pct, len(e))[1:]
    mdd = float((e / np.maximum.accumulate(e) - 1.0).min())
    cagr = float((e[-1] / e[0]) ** (1.0 / years) - 1.0)
    sd = float(ex.std(ddof=1))
    return {
        "cagr": cagr,
        "vol": float(r.std(ddof=1) * np.sqrt(252)),
        "sharpe": float(ex.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"),
        "max_dd": mdd,
        "calmar": cagr / -mdd if mdd < 0 else float("nan"),
        "years": float(years),
    }
