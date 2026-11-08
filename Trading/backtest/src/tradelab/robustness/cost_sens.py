"""Cost sensitivity: re-run with cost multipliers (and optional param variants such as +1 bar delay)."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from tradelab.analytics.metrics import daily_returns, sharpe_ratio


def _row(label: str, mult: float | None, res: Any, ppy: int) -> dict:
    r = daily_returns(res)
    return {"label": label, "cost_mult": mult, "total_return": float((1 + r).prod() - 1) if len(r) else float("nan"),
            "sharpe": sharpe_ratio(r, 0.0, ppy), "n_trades": 0 if res.trades is None else int(len(res.trades)),
            "net_pnl": float(res.trades["net_pnl"].sum()) if res.trades is not None and len(res.trades) and "net_pnl" in res.trades else float("nan"),
            "total_costs": float(pd.Series(res.costs_daily, dtype=float).sum()) if res.costs_daily is not None else float("nan")}


def cost_sensitivity(run_fn: Callable[..., Any], params: dict, mults: tuple[float, ...] = (0, 1, 2, 3),
                     variants: dict[str, dict] | None = None, periods_per_year: int = 252, **run_kw: Any) -> dict:
    """Returns {"table": DataFrame, "breakeven_cost_mult": float|None, "positive_at_2x": bool|None}.

    ``variants`` maps label -> param overrides (e.g. ``{"delay+1": {"delay_bars": 1}}``) run at 1x cost.
    Break-even multiplier: linear in log growth between the 0x and 1x runs (costs enter additively).
    """
    rows = [_row(f"{m:g}x", float(m), run_fn(params, cost_mult=float(m), **run_kw), periods_per_year) for m in mults]
    for label, ov in (variants or {}).items():
        rows.append(_row(label, None, run_fn({**params, **ov}, cost_mult=1.0, **run_kw), periods_per_year))
    t = pd.DataFrame(rows)
    by = t[t.cost_mult.notna()].set_index("cost_mult")
    be = None
    if 0.0 in by.index and 1.0 in by.index:
        # log growth is ~linear in the cost multiplier (costs compound daily), total return is not
        r0, r1 = (float(np.log1p(max(by.loc[m, "total_return"], -0.999999))) for m in (0.0, 1.0))
        if r0 > 0 and r0 > r1:
            be = float(r0 / (r0 - r1))
        elif r0 > 0 and r1 >= r0:
            be = float("inf")
    pos2 = bool(by.loc[2.0, "total_return"] > 0) if 2.0 in by.index else None
    return {"table": t, "breakeven_cost_mult": be, "positive_at_2x": pos2}
