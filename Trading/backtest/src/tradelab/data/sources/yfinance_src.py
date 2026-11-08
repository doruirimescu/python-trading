"""yfinance source (daily adjusted; intraday limited by Yahoo: 1m=7d, <=30m=60d)."""
from __future__ import annotations

import warnings

import pandas as pd

from ..base import normalise_bars
from ..calendar import ET, freq_to_timedelta, is_daily

_COLS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}


def normalise_yf_frame(raw: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Convert a yfinance history() frame to the canonical bar-end UTC frame (pure; unit-tested)."""
    df = raw.rename(columns=_COLS)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    if is_daily(freq):
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        idx = (idx.normalize() + pd.Timedelta(hours=16)).tz_localize(ET).tz_convert("UTC")
        df = df.copy()
        df.index = idx
        df.index.name = "ts"
        return df.sort_index()
    return normalise_bars(df, tz=ET, stamp="start", freq_td=freq_to_timedelta(freq))


class YFinanceSource:
    name = "yfinance"

    def load(self, symbol, start, end, freq, *, adjusted=True, **_):
        import yfinance as yf

        interval = "1d" if is_daily(freq) else freq.replace("h", "h")
        if not is_daily(freq):
            warnings.warn("yfinance intraday history is capped (1m: 7 days, <=30m: 60 days).", stacklevel=2)
        end_x = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if end else None
        raw = yf.Ticker(symbol).history(start=start, end=end_x, interval=interval, auto_adjust=adjusted, actions=False)
        if raw is None or len(raw) == 0:
            raise RuntimeError(f"yfinance returned no data for {symbol}")
        return normalise_yf_frame(raw, freq)

    def load_rate(self, symbol: str, start, end) -> pd.Series:
        """Annualised percent rate series (e.g. ^IRX) indexed by naive date."""
        import yfinance as yf

        raw = yf.Ticker(symbol).history(start=start, end=end, interval="1d", auto_adjust=False)
        s = raw["Close"]
        s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
        return s
