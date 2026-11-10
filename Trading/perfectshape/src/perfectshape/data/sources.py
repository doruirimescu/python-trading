"""Price sources -> aligned Panel. yfinance (cached, chunked bulk download) and synthetic (tests, no network)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np

from perfectshape.config import DataConfig
from perfectshape.data.cache import SeriesCache
from perfectshape.data.panel import Panel, align

log = logging.getLogger(__name__)


def load_panel(tickers: list[str], cfg: DataConfig, *, today: Optional[date] = None) -> Panel:
    if cfg.source == "synthetic":
        return synthetic_panel(tickers, **cfg.synthetic)
    series = load_yfinance(tickers, cfg, today=today or date.today())
    panel = align(series, max_gap_bars=cfg.max_gap_bars)
    if cfg.end is not None:
        keep = panel.dates <= np.datetime64(cfg.end, "D")
        panel = Panel(panel.dates[keep], panel.symbols, panel.close[keep])
    return panel


def load_yfinance(tickers: list[str], cfg: DataConfig, *, today: date) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    cache = SeriesCache(cfg.cache_dir, "yfinance")
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    stale: list[str] = []
    for t in tickers:
        e = cache.get(t)
        if e is not None and SeriesCache.is_fresh(e, today=today, end=cfg.end, years=cfg.years,
                                                  max_age_days=cfg.max_age_days):
            if not e.empty:
                out[t] = (e.dates, e.close)
        else:
            stale.append(t)
    log.info("yfinance: %d cached, %d to download", len(tickers) - len(stale), len(stale))
    if stale:
        end = cfg.end or today
        start = end - timedelta(days=int(cfg.years * 365.25) + 10)
        for i in range(0, len(stale), cfg.chunk_size):
            chunk = stale[i:i + cfg.chunk_size]
            log.info("downloading %d-%d of %d", i + 1, i + len(chunk), len(stale))
            got = _download_chunk(chunk, start, end + timedelta(days=1))
            for t in chunk:
                d, c = got.get(t, (np.array([], dtype="datetime64[D]"), np.array([])))
                cache.put(t, d, c, fetched_on=today, years=cfg.years)
                if len(d):
                    out[t] = (d, c)
    missing = [t for t in tickers if t not in out]
    if missing:
        log.warning("no data for %d tickers: %s", len(missing), ", ".join(missing[:20]))
    return out


def _download_chunk(tickers: list[str], start: date, end: date) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    import yfinance as yf

    df = yf.download(tickers, start=start.isoformat(), end=end.isoformat(), interval="1d", auto_adjust=True,
                     group_by="ticker", threads=True, progress=False)
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if df is None or df.empty:
        return out
    idx = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
    dates = idx.to_numpy(dtype="datetime64[D]")
    multi = getattr(df.columns, "nlevels", 1) > 1
    for t in tickers:
        try:
            col = df[(t, "Close")] if multi else df["Close"]
        except KeyError:
            continue
        c = col.to_numpy(dtype=np.float64)
        ok = np.isfinite(c) & (c > 0)
        if ok.sum():
            out[t] = (dates[ok], c[ok])
    return out


def synthetic_panel(tickers: list[str], *, n_bars: int = 1600, seed: int = 7, vol: float = 0.015,
                    plant: Optional[dict] = None, end: str = "2026-10-30") -> Panel:
    """Random-walk universe with optional planted shapes, for tests and offline smoke runs.

    ``plant``: {"uptrend": [A, B], "downtrend": [C, D], "range": [E, F]} makes the equal-weight average of
    each pair an exact straight trend / bounded oscillation over the last ``n_bars`` bars, while each
    member on its own wanders (a shared random walk is added to one and subtracted from the other).
    A dict value plants a basket ratio instead: {"shape": "uptrend"|"downtrend"|"range", "num": [...],
    "den": [...]} makes every numerator member track target x (equal-weight denominator basket).
    """
    rng = np.random.default_rng(seed)
    n = len(tickers)
    rets = rng.normal(0.0003, vol, size=(n_bars, n))
    close = 50.0 * np.exp(np.cumsum(rets, axis=0))
    t = np.arange(n_bars)
    for shape, pair in (plant or {}).items():
        if isinstance(pair, dict):
            _plant_ratio(close, tickers, t, rng, **pair)
            continue
        a, b = (tickers.index(x) for x in pair)
        wander = np.cumsum(rng.normal(0, 0.012, n_bars))
        wander -= wander[0]
        noise = rng.normal(0, 0.002, n_bars)
        if shape == "uptrend":
            target = 1.0 + 2.5 * t / n_bars
        elif shape == "downtrend":
            target = 1.0 - 0.6 * t / n_bars
        else:
            target = 1.0 + 0.12 * np.sin(2 * np.pi * t / 90.0)
        target = target + noise
        # 0.5 * (A + B) == target  with  A = target + wander_scaled, B = target - wander_scaled
        amp = 0.25 * target / max(1e-9, np.abs(wander).max())
        close[:, a] = 40.0 * (target + amp * wander)
        close[:, b] = 40.0 * (target - amp * wander)
    dates = np.busday_offset(np.datetime64(end, "D"), np.arange(-n_bars + 1, 1), roll="backward")
    return Panel(dates=dates.astype("datetime64[D]"), symbols=list(tickers), close=close)


def _plant_ratio(close: np.ndarray, tickers: list[str], t: np.ndarray, rng, *, shape: str, num: list[str],
                 den: list[str]) -> None:
    n_bars = len(t)
    # denominator members co-move (one shared walk + small noise), so the equal-weight denominator basket is
    # the same curve whatever bar it is normalised at, and the planted ratio is exact on every window
    d_idx = [tickers.index(x) for x in den]
    D = close[:, d_idx[0]] / close[0, d_idx[0]]
    for j, i in enumerate(d_idx):
        close[:, i] = (20.0 + 10.0 * j) * D * np.exp(rng.normal(0, 0.002, n_bars))
    if shape == "uptrend":
        target = np.exp(0.9 * t / n_bars)
    elif shape == "downtrend":
        target = np.exp(-0.9 * t / n_bars)
    else:
        target = 1.0 + 0.12 * np.sin(2 * np.pi * t / 90.0)
    for x in num:
        close[:, tickers.index(x)] = 30.0 * target * D * np.exp(rng.normal(0, 0.002, n_bars))
