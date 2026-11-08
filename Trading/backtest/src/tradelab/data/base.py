"""Data-source protocol and bar normalisation helpers."""
from __future__ import annotations

from typing import Protocol

import pandas as pd

OHLCV = ["open", "high", "low", "close", "volume"]
OPT = ["bid_vol", "ask_vol"]


class DataSource(Protocol):
    name: str

    def load(self, symbol: str, start: str | None, end: str | None, freq: str, *, adjusted: bool = True, **opts) -> pd.DataFrame:
        """Return UTC tz-aware, BAR-END stamped OHLCV(+bid_vol/ask_vol) frame, sorted, no session columns."""
        ...


def normalise_bars(df: pd.DataFrame, *, tz: str | None, stamp: str, freq_td: pd.Timedelta | None) -> pd.DataFrame:
    """Return UTC bar-end-stamped frame.

    tz: timezone of naive index (None => already tz-aware or UTC).
    stamp: 'end' (already bar end) | 'start' (bar open time -> add freq_td).
    """
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is None:
        idx = idx.tz_localize(tz or "UTC", ambiguous="infer", nonexistent="shift_forward") if tz and tz != "UTC" else idx.tz_localize("UTC")
    idx = idx.tz_convert("UTC").as_unit("ns")      # pandas>=3 may parse to us/ms: engines assume ns
    if stamp == "start":
        if freq_td is None:
            raise ValueError("freq_td required for bar-start stamps")
        idx = idx + freq_td
    out.index = idx
    out.index.name = "ts"
    out = out.sort_index()
    cols = [c for c in OHLCV + OPT if c in out.columns]
    if "volume" not in out.columns:
        out["volume"] = 0.0
        cols = [c for c in OHLCV + OPT if c in out.columns]
    keep = cols + [c for c in out.columns if c not in cols and c == "contract"]
    return out[keep]


def clip_range(df: pd.DataFrame, start: str | None, end: str | None, tz: str = "America/New_York") -> pd.DataFrame:
    """Clip by exchange-local calendar dates [start, end] (inclusive)."""
    if start is not None:
        lo = pd.Timestamp(start).tz_localize(tz).tz_convert("UTC")
        df = df[df.index > lo]  # bar-end stamps: a bar ending exactly at local midnight belongs to previous day
    if end is not None:
        hi = (pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize(tz).tz_convert("UTC")
        df = df[df.index <= hi]
    return df
