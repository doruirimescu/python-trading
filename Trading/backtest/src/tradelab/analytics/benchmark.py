"""Benchmark-relative metrics (alpha/beta/TE/IR/capture) on daily returns."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from ..util.span import years_span
from .metrics import aligned_rf, daily_returns, sharpe_ratio


def benchmark_metrics(result: Any, periods_per_year: int = 252) -> dict:
    b = getattr(result, "benchmark_daily", None)
    if b is None or len(b) == 0:
        return {}
    ppy = periods_per_year
    r = daily_returns(result)
    b = pd.Series(b, dtype=float).reindex(r.index)
    ok = b.notna()
    r, b = r[ok], b[ok]
    n = len(r)
    if n < 3:
        return {}
    rf = aligned_rf(result, r.index)
    ex_r, ex_b = r - rf, b - rf
    var_b = float(np.var(ex_b, ddof=1))
    beta = float(np.cov(ex_r, ex_b, ddof=1)[0, 1] / var_b) if var_b > 0 else float("nan")
    alpha_daily = float(ex_r.mean() - beta * ex_b.mean()) if np.isfinite(beta) else float("nan")
    active = r - b
    te = float(active.std(ddof=1) * math.sqrt(ppy))
    up, down = b > 0, b < 0
    up_cap = float(r[up].mean() / b[up].mean()) if up.any() and b[up].mean() != 0 else float("nan")
    down_cap = float(r[down].mean() / b[down].mean()) if down.any() and b[down].mean() != 0 else float("nan")
    tot_b = float((1 + b).prod() - 1)
    tot_r = float((1 + r).prod() - 1)
    yrs = years_span(r.index, ppy)
    cagr_b = (1 + tot_b) ** (1 / yrs) - 1 if 1 + tot_b > 0 else float("nan")
    cagr_r = (1 + tot_r) ** (1 / yrs) - 1 if 1 + tot_r > 0 else float("nan")
    curve_b = (1 + b).cumprod()
    return {
        "alpha_annual": alpha_daily * ppy, "beta": beta,
        "correlation": float(r.corr(b)), "tracking_error": te,
        "information_ratio": float(active.mean() * ppy / te) if te > 0 else float("nan"),
        "up_capture": up_cap, "down_capture": down_cap,
        "bh_total_return": tot_b, "bh_cagr": cagr_b, "bh_sharpe": sharpe_ratio(b, rf, ppy),
        "bh_max_drawdown": float((curve_b / curve_b.cummax() - 1).min()),
        "excess_total_return": tot_r - tot_b, "excess_cagr": cagr_r - cagr_b,
    }
