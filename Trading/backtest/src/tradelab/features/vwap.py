from __future__ import annotations

import pandas as pd


def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP using typical price; resets at each session_date. Causal."""
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    pv = tp * bars["volume"]
    g = bars["session_date"]
    cpv = pv.groupby(g).cumsum()
    cv = bars["volume"].groupby(g).cumsum()
    return cpv / cv.where(cv > 0)
