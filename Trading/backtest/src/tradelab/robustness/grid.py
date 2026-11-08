"""Parameter grid search (cartesian / random) with plateau score and returns matrix for PBO/DSR."""
from __future__ import annotations

import itertools
import math
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from tradelab.analytics.metrics import aligned_rf, compute_metrics, daily_returns, sharpe_ratio, sortino_ratio

Objective = str | Callable[[Any], float]


def score_result(result: Any, objective: Objective = "sharpe", periods_per_year: int = 252) -> float:
    """Objective value of a RunResult (higher is better). Fast paths avoid the full metric set."""
    if callable(objective):
        return float(objective(result))
    r = daily_returns(result)
    if len(r) < 2:
        return float("nan")
    # rf exactly as compute_metrics does, so the optimiser's objective == the number the report prints
    if objective == "sharpe":
        return sharpe_ratio(r, aligned_rf(result, r.index), periods_per_year)
    if objective == "sortino":
        return sortino_ratio(r, aligned_rf(result, r.index), periods_per_year)
    if objective == "total_return":
        return float((1 + r).prod() - 1)
    m = compute_metrics(result, periods_per_year=periods_per_year)
    for section in (m, m.get("trades", {}), m.get("rmultiple", {})):
        v = section.get(objective)
        if v is not None:
            return float(v)
    if objective == "expectancy_r":
        return float(m.get("rmultiple", {}).get("expectancy_r", float("nan")))
    raise KeyError(f"unknown objective {objective!r}")


def expand_grid(grid: dict[str, list], mode: str = "cartesian", n_random: int | None = None, seed: int = 42) -> list[dict]:
    keys = list(grid)
    combos = [dict(zip(keys, v)) for v in itertools.product(*[list(grid[k]) for k in keys])]
    if mode == "random" and n_random is not None and n_random < len(combos):
        rng = np.random.default_rng(seed)
        pick = sorted(rng.choice(len(combos), n_random, replace=False).tolist())
        combos = [combos[i] for i in pick]
    return combos


def _eval(args: tuple) -> tuple[dict, float, pd.Series, int, dict]:
    run_fn, params, objective, ppy, kw = args
    res = run_fn(params, **kw)
    r = daily_returns(res)
    n_tr = 0 if getattr(res, "trades", None) is None else len(res.trades)
    extra = {"total_return": float((1 + r).prod() - 1) if len(r) else float("nan")}
    return params, score_result(res, objective, ppy), r, n_tr, extra


@dataclass
class GridResult:
    table: pd.DataFrame                    # one row per config: params..., objective, n_trades, total_return, config_id
    returns_matrix: pd.DataFrame           # daily returns, columns = config_id
    objective: str
    param_names: list[str]
    best_params: dict = field(default_factory=dict)
    best_score: float = float("nan")
    n_trials: int = 0
    plateau_score: float = float("nan")
    sr_variance: float = float("nan")      # variance of per-period Sharpe across configs (for DSR)

    def to_dict(self) -> dict:
        return {"objective": self.objective, "best_params": self.best_params, "best_score": self.best_score,
                "n_trials": self.n_trials, "plateau_score": self.plateau_score, "sr_variance": self.sr_variance,
                "param_names": self.param_names}


def plateau_score(table: pd.DataFrame, grid: dict[str, list], objective_col: str = "objective") -> float:
    """Mean objective of the best point and its axis-adjacent grid neighbours / best objective.

    1.0 = flat plateau, small = isolated spike. NaN when best <= 0 or no neighbours exist.
    """
    keys = [k for k in grid if len(grid[k]) > 1]
    if not keys or table.empty:
        return float("nan")
    t = table.dropna(subset=[objective_col])
    if t.empty:
        return float("nan")
    best = t.loc[t[objective_col].idxmax()]
    if best[objective_col] <= 0:
        return float("nan")
    order = {k: list(grid[k]) for k in keys}
    pos = {k: order[k].index(best[k]) if best[k] in order[k] else None for k in keys}
    vals = [float(best[objective_col])]
    for k in keys:
        if pos[k] is None:
            continue
        for step in (-1, 1):
            j = pos[k] + step
            if 0 <= j < len(order[k]):
                mask = np.ones(len(t), bool)
                for kk in keys:
                    target = order[k][j] if kk == k else best[kk]
                    mask &= (t[kk] == target).to_numpy()
                if mask.any():
                    vals.append(float(t.loc[mask, objective_col].iloc[0]))
    if len(vals) < 2:
        return float("nan")
    return float(np.mean(vals) / best[objective_col])


def run_grid(run_fn: Callable[..., Any], grid: dict[str, list], objective: Objective = "sharpe", n_jobs: int = 1,
             seed: int = 42, *, mode: str = "cartesian", n_random: int | None = None, base_params: dict | None = None,
             start: Any = None, end: Any = None, cost_mult: float = 1.0, periods_per_year: int = 252) -> GridResult:
    """Evaluate ``run_fn`` over a parameter grid. ``n_jobs>1`` uses a process pool (run_fn must be picklable).

    ``base_params`` are merged under each grid point. ``start/end`` restrict the window (used by walk-forward).
    """
    combos = expand_grid(grid, mode, n_random, seed)
    kw = {"cost_mult": cost_mult}
    if start is not None:
        kw["start"] = start
    if end is not None:
        kw["end"] = end
    jobs = [(run_fn, {**(base_params or {}), **c}, objective, periods_per_year, kw) for c in combos]
    if n_jobs and n_jobs > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            out = list(ex.map(_eval, jobs))
    else:
        out = [_eval(j) for j in jobs]
    rows, cols = [], {}
    for i, (params, score, r, n_tr, extra) in enumerate(out):
        cid = f"c{i:04d}"
        rows.append({**{k: combos[i][k] for k in grid}, "objective": score, "n_trades": n_tr, **extra, "config_id": cid})
        cols[cid] = r
    table = pd.DataFrame(rows)
    rm = pd.DataFrame(cols).sort_index().fillna(0.0) if cols else pd.DataFrame()
    obj_name = objective if isinstance(objective, str) else getattr(objective, "__name__", "custom")
    res = GridResult(table=table, returns_matrix=rm, objective=obj_name, param_names=list(grid), n_trials=len(combos))
    ok = table.dropna(subset=["objective"]) if not table.empty else table
    if len(ok):
        b = ok.loc[ok["objective"].idxmax()]
        res.best_params = {k: _py(b[k]) for k in grid}
        res.best_score = float(b["objective"])
        res.plateau_score = plateau_score(table, grid)
    if rm.shape[1] > 1:
        sr = rm.mean() / rm.std(ddof=1).replace(0, np.nan)
        v = float(sr.var(ddof=1))
        res.sr_variance = v if math.isfinite(v) else float("nan")
    return res


def _py(v: Any) -> Any:
    return v.item() if hasattr(v, "item") else v


def heatmap_data(table: pd.DataFrame, x: str, y: str, value: str = "objective") -> pd.DataFrame:
    """Pivot (y rows x x cols); other parameters are collapsed with max()."""
    return table.pivot_table(index=y, columns=x, values=value, aggfunc="max")
