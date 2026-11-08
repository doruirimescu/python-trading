"""Walk-forward optimisation over sessions (rolling or anchored, purge between IS and OOS)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from tradelab.analytics.metrics import daily_returns, sharpe_ratio

from .grid import Objective, run_grid, score_result


def make_folds(n_sessions: int, is_len: int, oos_len: int, step: int | None = None, scheme: str = "rolling",
               purge: int = 0) -> list[dict[str, int]]:
    """Fold index ranges (half-open, in session positions). IS=[is_start,is_end), purge gap, OOS=[oos_start,oos_end).

    ``step`` defaults to ``oos_len`` so OOS windows tile without overlap. Anchored: IS always starts at 0.
    """
    if scheme not in ("rolling", "anchored"):
        raise ValueError("scheme must be rolling|anchored")
    step = step or oos_len
    folds = []
    k = 0
    while True:
        is_start = 0 if scheme == "anchored" else k * step
        is_end = is_start + is_len if scheme == "rolling" else is_len + k * step
        oos_start = is_end + purge
        oos_end = oos_start + oos_len
        if oos_end > n_sessions:
            break
        folds.append(dict(fold=k, is_start=is_start, is_end=is_end, oos_start=oos_start, oos_end=oos_end))
        k += 1
    return folds


@dataclass
class WalkForwardResult:
    folds: list[dict]
    oos_returns: pd.Series                 # stitched, non-overlapping OOS daily returns
    scheme: str
    objective: str
    efficiency: float = float("nan")       # mean(OOS obj) / mean(IS obj) per fold
    oos_sharpe: float = float("nan")
    initial_capital: float = 1.0
    meta: dict = field(default_factory=dict)

    @property
    def oos_equity(self) -> pd.Series:
        return self.initial_capital * (1 + self.oos_returns).cumprod()

    def to_dict(self) -> dict:
        return {"scheme": self.scheme, "objective": self.objective, "efficiency": self.efficiency,
                "oos_sharpe": self.oos_sharpe, "n_folds": len(self.folds), "folds": self.folds,
                "oos_total_return": float((1 + self.oos_returns).prod() - 1) if len(self.oos_returns) else None}


def walk_forward(run_fn: Callable[..., Any], grid: dict[str, list], sessions_index: pd.DatetimeIndex, is_len: int,
                 oos_len: int, step: int | None = None, scheme: str = "rolling", purge: int = 0,
                 objective: Objective = "sharpe", n_jobs: int = 1, seed: int = 42, periods_per_year: int = 252,
                 initial_capital: float = 1.0) -> WalkForwardResult:
    """For each fold: optimise ``grid`` on IS sessions, evaluate the winner on OOS sessions.

    ``run_fn`` receives ``start``/``end`` as tz-naive session-date Timestamps (inclusive).
    OOS returns are clipped to their OOS window and concatenated (stitched).
    """
    idx = pd.DatetimeIndex(sessions_index).sort_values().unique()
    folds = make_folds(len(idx), is_len, oos_len, step, scheme, purge)
    out_folds, parts, is_scores, oos_scores = [], [], [], []
    for f in folds:
        is_s, is_e = idx[f["is_start"]], idx[f["is_end"] - 1]
        o_s, o_e = idx[f["oos_start"]], idx[f["oos_end"] - 1]
        g = run_grid(run_fn, grid, objective, n_jobs, seed, start=is_s, end=is_e, periods_per_year=periods_per_year)
        best = g.best_params
        res = run_fn(best, start=o_s, end=o_e, cost_mult=1.0)
        r = daily_returns(res)
        r = r[(r.index >= o_s) & (r.index <= o_e)]
        oos_obj = score_result(res, objective, periods_per_year) if len(r) > 1 else float("nan")
        parts.append(r)
        is_scores.append(g.best_score)
        oos_scores.append(oos_obj)
        out_folds.append({**f, "is_start_date": is_s, "is_end_date": is_e, "oos_start_date": o_s, "oos_end_date": o_e,
                          "params": best, "is_objective": g.best_score, "oos_objective": oos_obj,
                          "oos_total_return": float((1 + r).prod() - 1) if len(r) else None,
                          "plateau_score": g.plateau_score})
    stitched = pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)
    stitched = stitched[~stitched.index.duplicated(keep="first")]
    isv, oosv = np.array(is_scores, float), np.array(oos_scores, float)
    ok = np.isfinite(isv) & np.isfinite(oosv)
    eff = float(oosv[ok].mean() / isv[ok].mean()) if ok.any() and isv[ok].mean() != 0 else float("nan")
    from tradelab.analytics.metrics import jsonable
    return WalkForwardResult(jsonable(out_folds), stitched, scheme, objective if isinstance(objective, str) else "custom",
                             eff, sharpe_ratio(stitched, 0.0, periods_per_year) if len(stitched) > 2 else float("nan"),
                             initial_capital, {"is_len": is_len, "oos_len": oos_len, "step": step or oos_len, "purge": purge})
