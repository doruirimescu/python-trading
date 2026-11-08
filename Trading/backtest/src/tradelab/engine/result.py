"""RunResult: the FROZEN contract between engines and analytics/robustness/report (ARCHITECTURE section 5)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..util.span import years_span

TRADE_COLUMNS = [
    "id", "symbol", "side", "qty", "entry_ts", "entry_px", "exit_ts", "exit_px", "exit_reason",
    "initial_stop", "target", "R_gross", "R_net", "MAE_R", "MFE_R", "MAE_usd", "MFE_usd",
    "bars_held", "session_date", "tag", "gross_pnl", "costs", "net_pnl",
    # additive, non-contract columns
    "commission", "slippage_cost",
]


@dataclass(frozen=True)
class RunResult:
    equity: pd.Series            # account value in currency, tz-aware UTC bar-end index
    returns_daily: pd.Series     # simple returns per session_date (DatetimeIndex, tz-naive dates)
    positions: pd.DataFrame      # bar index x symbol, signed qty or weight
    trades: pd.DataFrame         # columns as in TRADE_COLUMNS (may be empty, columns still present)
    costs_daily: pd.Series       # currency per session_date
    benchmark_daily: pd.Series | None   # benchmark simple returns per session_date
    rf_daily: pd.Series | None          # risk-free simple return per session_date
    initial_capital: float
    meta: dict                   # strategy, params, config_hash, data_fingerprint, freq, mode, seed


def empty_trades() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in TRADE_COLUMNS})


def daily_from_equity(equity: pd.Series, session_dates: np.ndarray | pd.Series, capital: float) -> pd.Series:
    """Simple return per session_date from bar-end equity (last bar of each session)."""
    s = pd.Series(equity.to_numpy(), index=pd.DatetimeIndex(np.asarray(session_dates)))
    eod = s.groupby(level=0).last()
    prev = np.r_[capital, eod.to_numpy()[:-1]]
    return pd.Series(eod.to_numpy() / prev - 1.0, index=eod.index, name="returns")


def daily_sum(values: np.ndarray, session_dates) -> pd.Series:
    s = pd.Series(np.asarray(values, float), index=pd.DatetimeIndex(np.asarray(session_dates)))
    return s.groupby(level=0).sum()


def basic_metrics(res: RunResult, periods_per_year: int = 252) -> dict:
    """Minimal metrics (CAGR / Sharpe / maxDD ...). Full analytics live in tradelab.analytics (WP-B)."""
    r = res.returns_daily.dropna()
    n = len(r)
    eq = (1 + r).cumprod() * res.initial_capital
    tot = float(eq.iloc[-1] / res.initial_capital - 1) if n else 0.0
    years = years_span(r.index, periods_per_year) if n else np.nan
    cagr = float((1 + tot) ** (1 / years) - 1) if n and years > 0 and (1 + tot) > 0 else float("nan")
    rf = res.rf_daily.reindex(r.index).fillna(0.0) if res.rf_daily is not None else 0.0
    ex = r - rf
    sd = ex.std(ddof=1) if n > 1 else np.nan
    sharpe = float(ex.mean() / sd * np.sqrt(periods_per_year)) if n > 1 and sd and sd > 0 else float("nan")
    peak = np.maximum.accumulate(np.r_[res.initial_capital, eq.to_numpy()])[1:] if n else np.array([])
    mdd = float((eq.to_numpy() / peak - 1).min()) if n else 0.0
    t = res.trades
    return {
        "total_return": tot, "cagr": cagr, "sharpe": sharpe, "max_drawdown": mdd,
        "ann_vol": float(r.std(ddof=1) * np.sqrt(periods_per_year)) if n > 1 else float("nan"),
        "n_days": int(n), "n_trades": int(len(t)),
        "final_equity": float(res.equity.iloc[-1]) if len(res.equity) else res.initial_capital,
        "total_costs": float(res.costs_daily.sum()),
        "net_pnl_trades": float(pd.to_numeric(t["net_pnl"]).sum()) if len(t) else 0.0,
    }
