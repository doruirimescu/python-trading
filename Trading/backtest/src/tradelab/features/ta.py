"""Basic causal technical helpers (all use data <= t only)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def rolling_zscore(s: pd.Series, n: int) -> pd.Series:
    return (s - s.rolling(n, min_periods=n).mean()) / s.rolling(n, min_periods=n).std()


def donchian(high: pd.Series, low: pd.Series, n: int) -> pd.DataFrame:
    """Channel of the PREVIOUS n bars (excludes current bar -> usable as breakout level)."""
    return pd.DataFrame({"upper": high.shift(1).rolling(n, min_periods=n).max(), "lower": low.shift(1).rolling(n, min_periods=n).min()})


def pct_rank(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
