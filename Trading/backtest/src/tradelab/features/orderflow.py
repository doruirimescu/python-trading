"""Order-flow features.

Real aggressor volumes (bid_vol = sell-initiated, ask_vol = buy-initiated) are used when present;
otherwise delta is APPROXIMATED (label ``approx_delta``) with the close-location-value method
(or tick rule).  Approximations are bar-level; true footprint (per-price imbalance) needs tick data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def has_real_delta(bars: pd.DataFrame) -> bool:
    return "bid_vol" in bars.columns and "ask_vol" in bars.columns and bars["ask_vol"].notna().any()


def delta(bars: pd.DataFrame, method: str = "auto") -> pd.Series:
    """Bar delta = buy volume - sell volume."""
    if method in ("auto", "real") and has_real_delta(bars):
        d = bars["ask_vol"] - bars["bid_vol"]
        d.name = "delta"
        return d
    if method == "real":
        raise ValueError("no bid_vol/ask_vol in bars")
    if method == "tick":
        sgn = np.sign(bars["close"].diff()).replace(0, np.nan).ffill().fillna(0.0)
        d = sgn * bars["volume"]
    else:  # clv
        rng = (bars["high"] - bars["low"]).replace(0, np.nan)
        clv = ((bars["close"] - bars["low"]) - (bars["high"] - bars["close"])) / rng
        d = clv.fillna(0.0) * bars["volume"]
    d.name = "delta"
    return d


def delta_features(bars: pd.DataFrame, method: str = "auto") -> pd.DataFrame:
    d = delta(bars, method)
    src = "real" if (method in ("auto", "real") and has_real_delta(bars)) else "approx_delta"
    vol = bars["volume"].replace(0, np.nan)
    out = pd.DataFrame({"delta": d, "delta_pct": d / vol}, index=bars.index)
    out["cum_delta"] = d.groupby(bars["session_date"]).cumsum() if "session_date" in bars else d.cumsum()
    out.attrs["delta_source"] = src
    out["delta_is_approx"] = src != "real"
    return out


def bar_imbalance(bars: pd.DataFrame) -> pd.DataFrame:
    """ask/bid and bid/ask volume ratios (bar level). Real data only; NaN when absent."""
    if not has_real_delta(bars):
        nan = pd.Series(np.nan, index=bars.index)
        return pd.DataFrame({"ask_bid_ratio": nan, "bid_ask_ratio": nan})
    a, b = bars["ask_vol"], bars["bid_vol"]
    return pd.DataFrame({"ask_bid_ratio": a / b.replace(0, np.nan), "bid_ask_ratio": b / a.replace(0, np.nan)})


def wick_fractions(bars: pd.DataFrame) -> pd.DataFrame:
    rng = (bars["high"] - bars["low"]).replace(0, np.nan)
    top = bars[["open", "close"]].max(axis=1)
    bot = bars[["open", "close"]].min(axis=1)
    return pd.DataFrame({"lower_wick": (bot - bars["low"]) / rng, "upper_wick": (bars["high"] - top) / rng, "body": (top - bot) / rng})


def absorption(bars: pd.DataFrame, *, wick_min: float = 0.4, delta_pct_min: float = 0.1, method: str = "auto") -> pd.DataFrame:
    """Heuristic absorption flags at bar close.

    abs_long : sellers pushed (delta_pct <= -delta_pct_min) into a long lower wick (>= wick_min of range)
               and the bar closed in its upper half => sell aggression absorbed.
    abs_short: mirror (buyers pushed, long upper wick, close in lower half).
    Uses real delta when available, else approx (check ``delta_is_approx``). With CLV-approx delta the
    delta sign is tied to the close location, so abs_long can then only fire from a weak CLV; treat as low-fidelity.
    """
    df = delta_features(bars, method)
    w = wick_fractions(bars)
    mid = (bars["high"] + bars["low"]) / 2
    abs_long = (df["delta_pct"] <= -delta_pct_min) & (w["lower_wick"] >= wick_min) & (bars["close"] >= mid)
    abs_short = (df["delta_pct"] >= delta_pct_min) & (w["upper_wick"] >= wick_min) & (bars["close"] <= mid)
    out = pd.DataFrame({"abs_long": abs_long.fillna(False), "abs_short": abs_short.fillna(False)}, index=bars.index)
    out["delta_is_approx"] = df["delta_is_approx"]
    return out
