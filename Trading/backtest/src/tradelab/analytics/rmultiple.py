"""R-multiple analytics: expectancy, SQN, streak probabilities, MAE/MFE, breakdowns."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import trade_col
from .trade_stats import _sorted_by_exit, streaks


def r_series(trades: pd.DataFrame | None, net: bool = True) -> pd.Series:
    """R per trade ordered by exit time (net R preferred, falls back to gross)."""
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    t = _sorted_by_exit(trades)
    col = trade_col(t, "R_net") if net else trade_col(t, "R_gross")
    if col is None:
        col = trade_col(t, "R_gross") if net else trade_col(t, "R_net")
    if col is None:
        return pd.Series(dtype=float)
    return pd.Series(col, dtype=float).dropna()


def prob_run_at_least(n: int, p: float, k: int) -> float:
    """P(at least one run of >= k successes in n iid Bernoulli(p) trials). Exact DP."""
    if k <= 0:
        return 1.0
    if n < k or p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    state = np.zeros(k)  # state[j] = P(current run == j, no k-run yet)
    state[0] = 1.0
    hit = 0.0
    for _ in range(n):
        new = np.zeros(k)
        new[0] = state.sum() * (1 - p)
        new[1:] = state[:-1] * p
        hit += state[k - 1] * p
        state = new
    return float(hit)


def sqn(r: pd.Series, cap: int | None = 100) -> float:
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    n = min(len(r), cap) if cap else len(r)
    return float(np.sqrt(n) * r.mean() / r.std(ddof=1))


def r_multiple_stats(trades: pd.DataFrame | None) -> dict:
    r = r_series(trades, net=True)
    out: dict = {"n": int(len(r))}
    if len(r) == 0:
        return out
    wins, losses = r[r > 0], r[r < 0]
    p_loss = float((r < 0).mean())
    out.update(
        expectancy_r=float(r.mean()), median_r=float(r.median()),
        std_r=float(r.std(ddof=1)) if len(r) > 1 else float("nan"),
        sqn=sqn(r, 100), sqn_uncapped=sqn(r, None),
        avg_win_r=float(wins.mean()) if len(wins) else float("nan"),
        avg_loss_r=float(losses.mean()) if len(losses) else float("nan"),
        best_r=float(r.max()), worst_r=float(r.min()), total_r=float(r.sum()),
        pct_r_ge_1=float((r >= 1).mean()), pct_r_le_minus1=float((r <= -1).mean()),
        r_per_trade_gross=float(r_series(trades, net=False).mean()),
    )
    sl = streaks((r < 0).to_numpy())
    out["max_consecutive_losses"] = sl["max"]
    out["loss_streak_prob_iid"] = {str(k): prob_run_at_least(len(r), p_loss, k) for k in (3, 5, 8, 10)}
    out["loss_streak_run_counts"] = {str(k): int(sum(1 for x in sl["runs"] if x >= k)) for k in (2, 3, 5, 8)}
    for name, cands in (("mae_r", ("MAE_R", "mae_r")), ("mfe_r", ("MFE_R", "mfe_r"))):
        c = trade_col(trades, *cands)
        if c is not None:
            out[f"avg_{name}"] = float(pd.Series(c, dtype=float).mean())
    return out


def r_histogram(trades: pd.DataFrame | None, bins: int = 30) -> pd.DataFrame:
    r = r_series(trades)
    if len(r) == 0:
        return pd.DataFrame(columns=["bin_left", "bin_right", "count"])
    cnt, edges = np.histogram(r.to_numpy(), bins=bins)
    return pd.DataFrame({"bin_left": edges[:-1], "bin_right": edges[1:], "count": cnt})


def r_equity(trades: pd.DataFrame | None) -> pd.Series:
    return r_series(trades).cumsum().reset_index(drop=True)


def _group_r(df: pd.DataFrame, key: pd.Series, name: str) -> pd.DataFrame:
    key = pd.Series(np.asarray(key), index=df.index, name=name)
    g = df.groupby(key, observed=True)
    out = pd.DataFrame({
        "n": g["r"].size(), "expectancy_r": g["r"].mean(), "total_r": g["r"].sum(),
        "hit_rate": g["r"].apply(lambda s: float((s > 0).mean())),
        "net_pnl": g["pnl"].sum(),
    })
    out.index.name = name
    return out


def r_breakdowns(trades: pd.DataFrame | None, tz: str = "UTC") -> dict[str, pd.DataFrame]:
    """R/PnL by exit reason, entry hour, entry weekday, trade number of the day, side."""
    if trades is None or len(trades) == 0:
        return {}
    t = _sorted_by_exit(trades).copy()
    r = trade_col(t, "R_net")
    if r is None:
        r = trade_col(t, "R_gross")
    pnl = trade_col(t, "net_pnl")
    df = pd.DataFrame({
        "r": pd.Series(r, dtype=float) if r is not None else np.nan,
        "pnl": pd.Series(pnl, dtype=float) if pnl is not None else np.nan,
    }, index=t.index)
    out: dict[str, pd.DataFrame] = {}
    er = trade_col(t, "exit_reason")
    if er is not None:
        out["by_exit_reason"] = _group_r(df, er.astype(str), "exit_reason")
    et = trade_col(t, "entry_ts")
    if et is not None:
        ts = pd.to_datetime(et, utc=True).dt.tz_convert(tz)
        out["by_entry_hour"] = _group_r(df, ts.dt.hour, "entry_hour")
        out["by_entry_weekday"] = _group_r(df, ts.dt.day_name(), "weekday")
    sd = trade_col(t, "session_date")
    if sd is not None:
        no = t.groupby(sd.astype(str)).cumcount() + 1
        out["by_trade_of_day"] = _group_r(df, no.clip(upper=5), "trade_of_day")
    side = trade_col(t, "side")
    if side is not None:
        out["by_side"] = _group_r(df, side.astype(str), "side")
    return out
