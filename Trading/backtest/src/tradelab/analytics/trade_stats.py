"""Trade-level statistics in currency (R-multiples live in rmultiple.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import trade_col


def streaks(flags: np.ndarray) -> dict:
    """Run-length stats of a boolean array: max run of True, current run, run-length list."""
    runs: list[int] = []
    cur = 0
    for f in flags:
        if f:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    cur_end = cur
    if cur:
        runs.append(cur)
    return {"max": max(runs) if runs else 0, "current": cur_end, "runs": runs}


def _sorted_by_exit(trades: pd.DataFrame) -> pd.DataFrame:
    ts = trade_col(trades, "exit_ts")
    if ts is not None:
        return trades.loc[pd.to_datetime(ts, utc=True).sort_values(kind="stable").index]
    return trades


def trade_stats(trades: pd.DataFrame | None, *, n_days: int | None = None) -> dict:
    """Hit rate, profit factor, payoff, expectancy, avg hold, streaks... based on ``net_pnl``."""
    out: dict = {"n_trades": 0}
    if trades is None or len(trades) == 0:
        return out
    t = _sorted_by_exit(trades)
    pnl = trade_col(t, "net_pnl")
    if pnl is None:
        pnl = trade_col(t, "gross_pnl")
    pnl = pd.Series(pnl, dtype=float).dropna()
    n = len(pnl)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gp, gl = float(wins.sum()), float(-losses.sum())
    avg_w = float(wins.mean()) if len(wins) else float("nan")
    avg_l = float(losses.mean()) if len(losses) else float("nan")
    out.update(
        n_trades=int(n), n_wins=int(len(wins)), n_losses=int(len(losses)),
        hit_rate=float(len(wins) / n) if n else float("nan"),
        profit_factor=gp / gl if gl > 0 else (float("inf") if gp > 0 else float("nan")),
        avg_win=avg_w, avg_loss=avg_l,
        payoff_ratio=avg_w / abs(avg_l) if len(losses) and len(wins) else float("nan"),
        expectancy=float(pnl.mean()), avg_trade=float(pnl.mean()),
        median_trade=float(pnl.median()), total_net_pnl=float(pnl.sum()),
        largest_win=float(pnl.max()), largest_loss=float(pnl.min()),
    )
    g = trade_col(t, "gross_pnl")
    if g is not None:
        out["total_gross_pnl"] = float(pd.Series(g, dtype=float).sum())
    c = trade_col(t, "costs")
    if c is not None:
        out["total_costs"] = float(pd.Series(c, dtype=float).sum())
    bh = trade_col(t, "bars_held")
    if bh is not None:
        out["avg_bars_held"] = float(pd.Series(bh, dtype=float).mean())
    et, xt = trade_col(t, "entry_ts"), trade_col(t, "exit_ts")
    if et is not None and xt is not None:
        hold = (pd.to_datetime(xt, utc=True) - pd.to_datetime(et, utc=True)).dt.total_seconds() / 3600.0
        out["avg_hold_hours"] = float(hold.mean())
    if n_days:
        out["trades_per_day"] = float(n / n_days)
    st_l = streaks((pnl < 0).to_numpy())
    st_w = streaks((pnl > 0).to_numpy())
    out.update(max_consecutive_losses=st_l["max"], max_consecutive_wins=st_w["max"],
               current_loss_streak=st_l["current"])
    side = trade_col(t, "side")
    pn_all = trade_col(t, "net_pnl")
    if side is not None and pn_all is not None:
        s = side.astype(str).str.lower()
        long_mask = s.isin(["long", "1", "1.0", "buy", "+1"])
        pn = pd.Series(pn_all, dtype=float)
        out["n_long"], out["n_short"] = int(long_mask.sum()), int((~long_mask).sum())
        out["pnl_long"], out["pnl_short"] = float(pn[long_mask].sum()), float(pn[~long_mask].sum())
    return out
