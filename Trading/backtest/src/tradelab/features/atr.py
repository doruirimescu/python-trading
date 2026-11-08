from __future__ import annotations

import pandas as pd


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.where(pc.notna(), high - low)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder ATR (causal, value at t uses bars <= t)."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
