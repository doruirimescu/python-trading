"""Panel: dict symbol -> Bars, aligned views, instrument specs, cash and benchmark."""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from ..config.schema import DataCfg
from ..util.hashing import frame_fingerprint, stable_hash
from . import cache
from .calendar import is_daily
from .continuous import stitch_continuous
from .instruments import InstrumentSpec, get_instrument
from .quality import DataQualityError, DataQualityReport, check_bars
from .resample import resample_bars
from .sessions import filter_rth, tag_sessions
from .sources import get_source


@dataclass
class Panel:
    bars: dict[str, pd.DataFrame]
    freq: str
    specs: dict[str, InstrumentSpec]
    cash: pd.Series | None = None            # simple rf return per session_date (naive dates)
    benchmark: pd.Series | None = None       # simple benchmark return per session_date
    quality: dict[str, DataQualityReport] = field(default_factory=dict)
    align: str = "intersection"
    ffill_limit: int = 3
    meta: dict = field(default_factory=dict)

    # ---- basics
    @property
    def symbols(self) -> list[str]:
        return list(self.bars)

    @property
    def primary(self) -> str:
        return next(iter(self.bars))

    def __getitem__(self, sym: str) -> pd.DataFrame:
        return self.bars[sym]

    @property
    def index(self) -> pd.DatetimeIndex:
        idxs = [b.index for b in self.bars.values()]
        if len(idxs) == 1:
            return idxs[0]
        out = idxs[0]
        for i in idxs[1:]:
            out = out.intersection(i) if self.align == "intersection" else out.union(i)
        return out

    def field(self, name: str) -> pd.DataFrame:
        """bar index x symbol matrix of one column on the common index (ffill-limited if union)."""
        idx = self.index
        cols = {s: b[name].reindex(idx) for s, b in self.bars.items()}
        out = pd.DataFrame(cols, index=idx)
        if self.align == "union" and self.ffill_limit:
            out = out.ffill(limit=self.ffill_limit)
        return out

    def session_dates(self) -> pd.Series:
        """session_date per bar on the common index (from the primary symbol)."""
        return self.bars[self.primary]["session_date"].reindex(self.index)

    # ---- slicing (never reindexes data; used by engines / robustness / causality)
    def with_bars(self, bars: dict[str, pd.DataFrame]) -> "Panel":
        return replace(self, bars=bars)

    def head(self, n: int) -> "Panel":
        return self.with_bars({s: b.iloc[:n] for s, b in self.bars.items()})

    def slice_ts(self, start=None, end=None) -> "Panel":
        def f(b):
            if start is not None:
                b = b[b.index >= pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tz is None else b.index >= pd.Timestamp(start)]
            if end is not None:
                b = b[b.index <= pd.Timestamp(end, tz="UTC") if pd.Timestamp(end).tz is None else b.index <= pd.Timestamp(end)]
            return b
        return self.with_bars({s: f(b) for s, b in self.bars.items()})

    def slice_sessions(self, start=None, end=None) -> "Panel":
        """Inclusive slice by session_date (naive dates)."""
        def f(b):
            sd = b["session_date"]
            m = np.ones(len(b), bool)
            if start is not None:
                m &= (sd >= pd.Timestamp(start)).to_numpy()
            if end is not None:
                m &= (sd <= pd.Timestamp(end)).to_numpy()
            return b[m]
        p = self.with_bars({s: f(b) for s, b in self.bars.items()})
        for a in ("cash", "benchmark"):
            ser = getattr(self, a)
            if ser is not None:
                if start is not None:
                    ser = ser[ser.index >= pd.Timestamp(start)]
                if end is not None:
                    ser = ser[ser.index <= pd.Timestamp(end)]
                setattr(p, a, ser)
        return p

    def fingerprint(self) -> str:
        return stable_hash({s: frame_fingerprint(b[["open", "high", "low", "close", "volume"]]) for s, b in self.bars.items()}, 16)


# ---------------------------------------------------------------------------------------------
def daily_returns_from_bars(b: pd.DataFrame) -> pd.Series:
    close = b.groupby("session_date")["close"].last()
    return close.pct_change().dropna()


def _prepare_symbol(symbol: str, cfg: DataCfg, spec: InstrumentSpec, root) -> tuple[pd.DataFrame, DataQualityReport]:
    src = get_source(cfg.source)
    base_freq = cfg.base_freq or cfg.freq
    opts = dict(cfg.options)

    def fetch():
        return src.load(symbol, cfg.start, cfg.end, base_freq, adjusted=cfg.adjusted, **opts)

    if cfg.source == "yfinance":
        key = cache.cache_key("yfinance", symbol, cfg.start, cfg.end, base_freq, cfg.adjusted, cfg.session)
        df = cache.load_or_fetch("yfinance", key, fetch, refresh=cfg.refresh, root=root)
    else:
        df = fetch()
    df = tag_sessions(df, spec, base_freq)
    if "contract" in df.columns and cfg.continuous != "none":
        df = stitch_continuous(df, method=cfg.continuous, adjust=cfg.adjust)
        df = tag_sessions(df, spec, base_freq)
    if base_freq != cfg.freq:
        df = resample_bars(df, spec, base_freq, cfg.freq)
    if not is_daily(cfg.freq) and cfg.session == "rth":
        df = filter_rth(df, spec)
    rep = check_bars(df, spec, cfg.freq, symbol)
    if cfg.strict_quality and not rep.ok:
        raise DataQualityError(f"{symbol}: {rep.issues}")
    for i in rep.issues:
        if i["severity"] == "error":
            warnings.warn(f"data quality {symbol}: {i}")
    return df, rep


def load_panel(cfg: DataCfg, *, cache_root=None) -> Panel:
    bars, specs, quality = {}, {}, {}
    for s in cfg.symbols:
        spec = get_instrument(s, cfg.instruments.get(s))
        df, rep = _prepare_symbol(s, cfg, spec, cache_root)
        bars[s], specs[s], quality[s] = df, spec, rep
    cash = None
    all_days = pd.DatetimeIndex(sorted(set().union(*[set(b["session_date"].unique()) for b in bars.values()])))
    if isinstance(cfg.cash, (int, float)):
        cash = pd.Series((1 + float(cfg.cash)) ** (1 / 252) - 1, index=all_days)
    elif isinstance(cfg.cash, str) and cfg.source == "yfinance":
        r = get_source("yfinance").load_rate(cfg.cash, cfg.start, cfg.end)
        cash = ((1 + r / 100.0) ** (1 / 252) - 1).reindex(all_days, method="ffill").fillna(0.0)
    bench = None
    if cfg.benchmark:
        bcfg = cfg.model_copy(update={"symbols": [cfg.benchmark], "freq": "1d", "base_freq": None, "benchmark": None, "cash": None})
        bb, _ = _prepare_symbol(cfg.benchmark, bcfg, get_instrument(cfg.benchmark), cache_root)
        bench = daily_returns_from_bars(bb)
    p = Panel(bars, cfg.freq, specs, cash, bench, quality, cfg.align, cfg.ffill_limit)
    p.meta["fingerprint"] = p.fingerprint()
    return p
