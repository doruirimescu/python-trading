"""Synthetic RunResult fixtures (local dataclass with the frozen section-5 fields)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADE_COLS = [
    "id", "symbol", "side", "qty", "entry_ts", "entry_px", "exit_ts", "exit_px", "exit_reason", "initial_stop",
    "target", "R_gross", "R_net", "MAE_R", "MFE_R", "MAE_usd", "MFE_usd", "bars_held", "session_date", "tag",
    "gross_pnl", "costs", "net_pnl",
]


@dataclass(frozen=True)
class SynthResult:
    equity: pd.Series
    returns_daily: pd.Series
    positions: pd.DataFrame
    trades: pd.DataFrame
    costs_daily: pd.Series
    benchmark_daily: pd.Series | None
    rf_daily: pd.Series | None
    initial_capital: float
    meta: dict = field(default_factory=dict)


def make_trades(n: int = 60, seed: int = 3, start: str = "2024-01-02") -> pd.DataFrame:
    """Intraday-style trades: one per business day, 14:35 UTC entry, ~2h hold."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=n)
    R = np.round(rng.normal(0.15, 1.0, n).clip(-1.2, 4.0), 3)
    risk = 100.0
    rows = []
    for i, d in enumerate(days):
        et = pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=14, minutes=35)
        xt = et + pd.Timedelta(hours=2)
        cost = 4.0
        gross = R[i] * risk + cost
        reason = "target" if R[i] > 1 else ("stop" if R[i] < -0.9 else "time")
        rows.append(dict(
            id=i, symbol="MNQ", side="long" if i % 3 else "short", qty=1, entry_ts=et, entry_px=100.0 + i,
            exit_ts=xt, exit_px=100.0 + i + R[i], exit_reason=reason, initial_stop=99.0 + i, target=102.0 + i,
            R_gross=gross / risk, R_net=R[i], MAE_R=-abs(rng.normal(0.4, 0.2)), MFE_R=abs(rng.normal(1.0, 0.5)),
            MAE_usd=-40.0, MFE_usd=100.0, bars_held=24, session_date=pd.Timestamp(d).normalize(), tag="",
            gross_pnl=gross, costs=cost, net_pnl=R[i] * risk))
    return pd.DataFrame(rows, columns=TRADE_COLS)


def make_result(n_days: int = 500, seed: int = 7, mu: float = 0.0006, sigma: float = 0.01,
                with_bench: bool = True, with_trades: bool = True, start: str = "2022-01-03",
                initial_capital: float = 100_000.0) -> SynthResult:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=n_days)
    r = pd.Series(rng.normal(mu, sigma, n_days), index=days, name="ret")
    bench = pd.Series(rng.normal(0.0004, 0.009, n_days) + 0.3 * r.to_numpy(), index=days) if with_bench else None
    rf = pd.Series(0.00005, index=days)
    # daily bars stamped at 21:00 UTC (bar end)
    eq_idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=21) for d in days])
    equity = pd.Series(initial_capital * (1 + r).cumprod().to_numpy(), index=eq_idx, name="equity")
    pos = pd.DataFrame({"MNQ": np.where(rng.random(n_days) > 0.3, 1.0, 0.0)}, index=eq_idx)
    trades = make_trades(min(60, n_days), seed + 1, start) if with_trades else pd.DataFrame(columns=TRADE_COLS)
    costs = pd.Series(2.0, index=days)
    return SynthResult(equity, r, pos, trades, costs, bench, rf, initial_capital,
                       {"strategy": "synth", "params": {}, "freq": "1d", "mode": "event", "seed": seed})


def result_from_returns(r: pd.Series, initial_capital: float = 100_000.0, trades: pd.DataFrame | None = None) -> SynthResult:
    eq_idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=21) for d in r.index])
    equity = pd.Series(initial_capital * (1 + r).cumprod().to_numpy(), index=eq_idx)
    return SynthResult(equity, r, pd.DataFrame({"X": 1.0}, index=eq_idx),
                       trades if trades is not None else pd.DataFrame(columns=TRADE_COLS),
                       pd.Series(0.0, index=r.index), None, None, initial_capital, {"strategy": "x"})
