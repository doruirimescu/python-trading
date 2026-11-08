"""CSV / Parquet sources with timestamp-convention presets."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..base import clip_range, normalise_bars
from ..calendar import ET, freq_to_timedelta, is_daily

PRESETS: dict[str, dict] = {
    # Databento ts_event = bar OPEN time (UTC). Prices float (to_df pretty) or fixed 1e-9 ints (set price_scale).
    "databento_ohlcv_1m": {"ts_col": "ts_event", "tz": "UTC", "stamp": "start", "freq": "1m"},
    "databento_ohlcv_1s": {"ts_col": "ts_event", "tz": "UTC", "stamp": "start", "freq": "1s"},
    # FirstRate Data: headerless "YYYY-MM-DD HH:MM:SS,o,h,l,c,v" in US/Eastern, bar OPEN stamps
    "firstrate": {"ts_col": "ts", "tz": ET, "stamp": "start", "header": None, "names": ["ts", "open", "high", "low", "close", "volume"]},
    # IBKR TWS/IBKR-gateway export: 'date' column, exchange-local, bar OPEN stamps
    "ibkr_export": {"ts_col": "date", "tz": ET, "stamp": "start", "columns": {"barCount": "bar_count"}},
    "generic_end": {"ts_col": "ts", "tz": "UTC", "stamp": "end"},
}


def read_table(path: Path, fmt: str, preset: dict) -> pd.DataFrame:
    if fmt == "csv":
        kw = {}
        if "header" in preset:
            kw["header"] = preset["header"]
        if "names" in preset:
            kw["names"] = preset["names"]
        return pd.read_csv(path, **kw)
    return pd.read_parquet(path)


def normalise_table(raw: pd.DataFrame, freq: str, preset: dict, opts: dict) -> pd.DataFrame:
    """Pure transform: raw table -> canonical UTC bar-end frame."""
    df = raw.copy()
    cols = {**preset.get("columns", {}), **opts.get("columns", {})}
    df = df.rename(columns=cols)
    ts_col = opts.get("ts_col") or preset.get("ts_col")
    if ts_col and ts_col in df.columns:
        df = df.set_index(ts_col)
    elif not isinstance(df.index, pd.DatetimeIndex):
        for c in ("ts", "ts_event", "timestamp", "datetime", "date", "Date", "time"):
            if c in df.columns:
                df = df.set_index(c)
                break
    tz = opts.get("tz", preset.get("tz", "UTC"))
    stamp = opts.get("stamp", preset.get("stamp", "end"))
    idx = pd.to_datetime(df.index, utc=(tz == "UTC")) if not isinstance(df.index, pd.DatetimeIndex) else df.index
    if getattr(idx, "tz", None) is None and tz != "UTC":
        pass
    df.index = idx
    df.columns = [str(c).lower() for c in df.columns]
    scale = opts.get("price_scale", 1.0)
    if scale != 1.0:
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] * scale
    if is_daily(freq):
        # daily rows: stamp at session close 16:00 exchange tz regardless of source stamp.
        # The row's DATE is the calendar date in the source's own timezone: UTC-midnight stamps (Databento
        # daily) mean "the session of that UTC date", so the UTC date is taken directly (converting it to
        # ET would land on the previous evening, i.e. the previous session, a one-day look-ahead).
        d = pd.DatetimeIndex(df.index)
        if d.tz is not None:
            d = d.tz_convert(tz).tz_localize(None)
        d = d.normalize() + pd.Timedelta(hours=16)
        df.index = d.tz_localize(ET).tz_convert("UTC").as_unit("ns")
        df.index.name = "ts"
        keep = [c for c in ("open", "high", "low", "close", "volume", "bid_vol", "ask_vol") if c in df.columns]
        out = df[keep].sort_index()
        if "volume" not in out:
            out["volume"] = 0.0
        return out
    fr = freq_to_timedelta(freq)
    out = normalise_bars(df, tz=tz, stamp=stamp, freq_td=fr)
    if "contract" in raw.columns:
        out["contract"] = raw["contract"].to_numpy()[: len(out)] if len(raw) == len(out) else None
    return out


class _FileSource:
    fmt = "csv"
    name = "csv"

    def load(self, symbol, start, end, freq, *, adjusted=True, path=None, preset=None, **opts):
        if path is None:
            raise ValueError(f"{self.name} source needs options.path (may contain {{symbol}})")
        p = Path(str(path).format(symbol=symbol)).expanduser()
        pr = PRESETS[preset] if preset else {}
        raw = read_table(p, self.fmt, pr)
        if "symbol" in raw.columns and (raw["symbol"] == symbol).any():
            raw = raw[raw["symbol"] == symbol]
        df = normalise_table(raw, freq, pr, opts)
        return clip_range(df, start, end)


class CsvSource(_FileSource):
    fmt = "csv"
    name = "csv"


class ParquetSource(_FileSource):
    fmt = "parquet"
    name = "parquet"
