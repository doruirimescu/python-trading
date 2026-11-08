"""Stationary block bootstrap of daily returns and trade-resample Monte Carlo."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class SimResult:
    summary: dict
    samples: pd.DataFrame

    def to_dict(self) -> dict:
        return self.summary


def auto_block_length(T: int) -> int:
    """Heuristic mean block length ~ T^(1/3) (>=2); documented simplification of Politis-White."""
    return max(2, int(round(T ** (1 / 3))))


def _stationary_indices(T: int, n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    p = 1.0 / mean_block
    idx = np.empty((n, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, n)
    restart = rng.random((n, T)) < p
    starts = rng.integers(0, T, (n, T))
    for t in range(1, T):
        idx[:, t] = np.where(restart[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def _max_dd(paths_ret: np.ndarray) -> np.ndarray:
    curve = np.cumprod(1.0 + paths_ret, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((curve.shape[0], 1)), curve], axis=1), axis=1)[:, 1:]
    return (curve / peak - 1.0).min(axis=1)


def _q(a: np.ndarray, name: str) -> dict:
    return {f"{name}_mean": float(np.mean(a)), f"{name}_p05": float(np.quantile(a, .05)),
            f"{name}_p50": float(np.quantile(a, .5)), f"{name}_p95": float(np.quantile(a, .95))}


def block_bootstrap(returns: pd.Series, n: int = 2000, block: int | str = "auto", seed: int = 42,
                    periods_per_year: int = 252) -> SimResult:
    """Stationary (Politis-Romano) bootstrap of daily returns. Same ``seed`` -> identical output."""
    x = np.asarray(pd.Series(returns, dtype=float).dropna())
    T = len(x)
    if T < 10:
        return SimResult({"n": 0, "note": "too few observations"}, pd.DataFrame())
    b = auto_block_length(T) if block == "auto" else int(block)
    rng = np.random.default_rng(seed)
    idx = _stationary_indices(T, n, b, rng)
    paths = x[idx]
    mu, sd = paths.mean(axis=1), paths.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(sd > 0, mu / sd * math.sqrt(periods_per_year), np.nan)
    total = np.prod(1 + paths, axis=1) - 1
    years = T / periods_per_year
    cagr = np.where(total > -1, (1 + total) ** (1 / years) - 1, -1.0)
    mdd = _max_dd(paths)
    samples = pd.DataFrame({"sharpe": sharpe, "total_return": total, "cagr": cagr, "max_drawdown": mdd})
    s: dict[str, Any] = {"n": int(n), "block": int(b), "seed": int(seed), "T": int(T),
                         "prob_sharpe_gt_0": float(np.nanmean(sharpe > 0)),
                         "prob_total_return_gt_0": float((total > 0).mean())}
    s.update(_q(sharpe, "sharpe"))
    s.update(_q(total, "total_return"))
    s.update(_q(mdd, "max_drawdown"))
    s["observed_sharpe"] = float(x.mean() / x.std(ddof=1) * math.sqrt(periods_per_year)) if x.std(ddof=1) > 0 else float("nan")
    return SimResult(s, samples)


def trade_monte_carlo(trades: pd.DataFrame, n: int = 2000, seed: int = 42, initial_capital: float = 100_000.0,
                      ruin_level: float = 0.5, pnl_col: str = "net_pnl") -> SimResult:
    """Resample trade P&L (with replacement, same count) -> equity paths in currency.

    Reports max-drawdown (fraction of running peak), final equity, and risk of ruin
    = P(equity ever <= ``ruin_level`` * initial_capital).
    """
    lower = {str(c).lower(): c for c in trades.columns} if trades is not None else {}
    col = lower.get(pnl_col.lower())
    if col is None or len(trades) < 5:
        return SimResult({"n": 0, "note": "too few trades / no pnl"}, pd.DataFrame())
    pnl = trades[col].astype(float).dropna().to_numpy()
    k = len(pnl)
    rng = np.random.default_rng(seed)
    draw = pnl[rng.integers(0, k, (n, k))]
    eq = initial_capital + np.cumsum(draw, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.full((n, 1), initial_capital), eq], axis=1), axis=1)[:, 1:]
    dd = np.where(peak > 0, eq / peak - 1.0, -1.0).min(axis=1)
    final = eq[:, -1]
    ruined = (eq.min(axis=1) <= ruin_level * initial_capital)
    samples = pd.DataFrame({"final_equity": final, "max_drawdown": dd, "ruined": ruined})
    s: dict[str, Any] = {"n": int(n), "n_trades": int(k), "seed": int(seed), "initial_capital": float(initial_capital),
                         "risk_of_ruin": float(ruined.mean()), "ruin_level": float(ruin_level),
                         "prob_final_gt_initial": float((final > initial_capital).mean())}
    s.update(_q(final, "final_equity"))
    s.update(_q(dd, "max_drawdown"))
    return SimResult(s, samples)
