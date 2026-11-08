"""Aggregate Databento ``trades`` records into order-flow bars (+ optional price-level footprint).

Side semantics (Databento ``side`` = the AGGRESSOR side, verified against databento_dbn docs):
``'A'`` = Ask side = SELL aggressor (hits the bid)  -> counted in ``bid_vol``
``'B'`` = Bid side = BUY  aggressor (lifts the ask) -> counted in ``ask_vol``
``'N'`` = none/unknown -> in ``volume`` only (so ``volume >= bid_vol + ask_vol``).
This matches the framework convention (bid_vol = volume traded at the bid, ask_vol = at the ask).

Output bars are UTC and BAR-END stamped (index ``ts``): a trade with ts_event in [T, T+freq) belongs to
the bar stamped T+freq. Parquet writers (see ``write_bars_parquet``) store the bar OPEN as ``ts_event`` so the
file loads through the ``databento_ohlcv_1m`` preset unchanged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .calendar import ET

BAR_COLS = ["open", "high", "low", "close", "volume", "bid_vol", "ask_vol", "n_trades", "instrument_id"]
FP_COLS = ["price", "bid_vol", "ask_vol"]


@dataclass
class OrderflowResult:
    bars: pd.DataFrame            # index ts (bar end, UTC)
    footprint: pd.DataFrame | None  # columns ts (bar end, UTC), price, bid_vol, ask_vol


def parse_hhmm(s: str) -> pd.Timedelta:
    h, m = s.split(":")[:2]
    return pd.Timedelta(hours=int(h), minutes=int(m))


def parse_window(w: str | tuple | list) -> tuple[str, str]:
    """'09:00-11:30' | ('09:00','11:30') -> ('09:00', '11:30')."""
    if isinstance(w, str):
        a, b = w.split("-")
        return a.strip(), b.strip()
    return str(w[0]), str(w[1])


def _prep(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades
    if "ts_event" in df.columns:
        df = df.set_index("ts_event")
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df = df.copy()
    df.index = idx
    df.index.name = "ts_event"
    # stable sort keeps exchange sequence for equal timestamps (open/close correctness)
    return df.iloc[np.argsort(df.index.values, kind="stable")]


def filter_time_of_day(df: pd.DataFrame, window, tz: str = ET) -> pd.DataFrame:
    """Keep rows whose exchange-local time-of-day lies in [start, end) (DST-safe)."""
    a, b = parse_window(window)
    local = df.index.tz_convert(tz)
    tod = local - local.normalize()
    m = (tod >= parse_hhmm(a)) & (tod < parse_hhmm(b))
    return df[np.asarray(m)]


def _bars(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    step = pd.Timedelta(freq)
    bin_ = df.index.floor(freq)
    size = df["size"].astype("float64")
    side = df["side"].astype(str)
    g = pd.DataFrame({
        "price": df["price"].astype("float64").to_numpy(),
        "size": size.to_numpy(),
        "bid": np.where(side.to_numpy() == "A", size.to_numpy(), 0.0),
        "ask": np.where(side.to_numpy() == "B", size.to_numpy(), 0.0),
        "iid": df["instrument_id"].to_numpy() if "instrument_id" in df.columns else 0,
    }, index=bin_)
    agg = g.groupby(level=0, sort=True).agg(
        open=("price", "first"), high=("price", "max"), low=("price", "min"), close=("price", "last"),
        volume=("size", "sum"), bid_vol=("bid", "sum"), ask_vol=("ask", "sum"),
        n_trades=("price", "size"), instrument_id=("iid", "last"),
    )
    agg.index = agg.index + step
    agg.index.name = "ts"
    return agg[BAR_COLS]


def _footprint(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    step = pd.Timedelta(freq)
    side = df["side"].astype(str).to_numpy()
    size = df["size"].astype("float64").to_numpy()
    g = pd.DataFrame({
        "ts": df.index.floor(freq) + step,
        "price": df["price"].astype("float64").round(6).to_numpy(),
        "bid_vol": np.where(side == "A", size, 0.0),
        "ask_vol": np.where(side == "B", size, 0.0),
    })
    return g.groupby(["ts", "price"], sort=True, as_index=False)[["bid_vol", "ask_vol"]].sum()


def aggregate_trades(trades: pd.DataFrame, *, freq: str = "1min", footprint_freq: str | None = None,
                     tod_window=None, tz: str = ET) -> OrderflowResult:
    """trades (ts_event, price, size, side[, instrument_id]) -> bars (+ footprint at ``footprint_freq``)."""
    if len(trades) == 0:
        return OrderflowResult(pd.DataFrame(columns=BAR_COLS, index=pd.DatetimeIndex([], tz="UTC", name="ts")),
                               pd.DataFrame(columns=["ts"] + FP_COLS) if footprint_freq else None)
    df = _prep(trades)
    if tod_window:
        df = filter_time_of_day(df, tod_window, tz)
    if len(df) == 0:
        return aggregate_trades(trades.iloc[:0], freq=freq, footprint_freq=footprint_freq)
    return OrderflowResult(_bars(df, freq), _footprint(df, footprint_freq) if footprint_freq else None)


def combine_bars(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge time-ordered partial aggregations (e.g. trade batches) covering the same bars."""
    parts = [p for p in parts if len(p)]
    if not parts:
        return pd.DataFrame(columns=BAR_COLS, index=pd.DatetimeIndex([], tz="UTC", name="ts"))
    df = pd.concat(parts)
    out = df.groupby(level=0, sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), bid_vol=("bid_vol", "sum"), ask_vol=("ask_vol", "sum"),
        n_trades=("n_trades", "sum"), instrument_id=("instrument_id", "last"))
    out.index.name = "ts"
    return out[BAR_COLS]


def combine_footprint(parts: list[pd.DataFrame]) -> pd.DataFrame:
    parts = [p for p in parts if len(p)]
    if not parts:
        return pd.DataFrame(columns=["ts"] + FP_COLS)
    return pd.concat(parts).groupby(["ts", "price"], sort=True, as_index=False)[["bid_vol", "ask_vol"]].sum()


# ---------------------------------------------------------------------------------------------- parquet I/O
def atomic_to_parquet(df: pd.DataFrame, path: Path, **kw) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, **kw)
    os.replace(tmp, path)


def bars_to_ohlcv_frame(bars: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Bar-end indexed bars -> frame with ``ts_event`` = bar OPEN (preset ``databento_ohlcv_1m`` compatible)."""
    out = bars.copy()
    out.insert(0, "ts_event", out.index - pd.Timedelta(freq))
    return out.reset_index(drop=True)


def write_bars_parquet(bars: pd.DataFrame, path: Path, freq: str = "1min") -> None:
    atomic_to_parquet(bars_to_ohlcv_frame(bars, freq), path, compression="zstd")


def write_footprint_parquet(fp: pd.DataFrame, path: Path) -> None:
    """Compact footprint: float64 price (rounded 1e-6), float32 volumes, zstd, sorted by (ts, price)."""
    f = fp.copy()
    f["bid_vol"] = f["bid_vol"].astype("float32")
    f["ask_vol"] = f["ask_vol"].astype("float32")
    atomic_to_parquet(f, path, compression="zstd")
