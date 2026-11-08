"""Aligned close-price panel (bars x symbols)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Panel:
    dates: np.ndarray        # datetime64[D], ascending, length T
    symbols: list[str]       # length n
    close: np.ndarray        # float64 (T, n); NaN where an instrument has no bar

    def __post_init__(self):
        self.close = np.asarray(self.close, dtype=np.float64)
        if self.close.shape != (len(self.dates), len(self.symbols)):
            raise ValueError(f"close shape {self.close.shape} != ({len(self.dates)}, {len(self.symbols)})")

    @property
    def n_bars(self) -> int:
        return len(self.dates)

    def complete_columns(self, start: int, stop: int) -> np.ndarray:
        """Indices of symbols with a valid positive price on every bar in [start, stop)."""
        block = self.close[start:stop]
        ok = np.isfinite(block).all(axis=0) & (block > 0).all(axis=0)
        return np.flatnonzero(ok)


def align(series: dict[str, tuple[np.ndarray, np.ndarray]], *, max_gap_bars: int = 3,
          min_coverage: float = 0.5) -> Panel:
    """Union-align per-symbol (dates, close) series onto a common calendar.

    The calendar is every date on which at least ``min_coverage`` of the symbols traded (drops stray
    holiday bars of a few listings). Holes of up to ``max_gap_bars`` are forward-filled; longer ones stay NaN.
    """
    symbols = [s for s, (d, _) in series.items() if len(d)]
    if not symbols:
        raise ValueError("no data to align")
    all_dates, counts = np.unique(np.concatenate([series[s][0] for s in symbols]), return_counts=True)
    keep = counts >= max(1, int(np.ceil(min_coverage * len(symbols))))
    dates = all_dates[keep]
    close = np.full((len(dates), len(symbols)), np.nan)
    for j, s in enumerate(symbols):
        d, c = series[s]
        pos = np.searchsorted(dates, d)
        hit = (pos < len(dates)) & (dates[np.minimum(pos, len(dates) - 1)] == d)
        close[pos[hit], j] = c[hit]
    if max_gap_bars > 0:
        close = _ffill_limited(close, max_gap_bars)
    return Panel(dates=dates, symbols=symbols, close=close)


def _ffill_limited(a: np.ndarray, limit: int) -> np.ndarray:
    out = a.copy()
    T = a.shape[0]
    valid = np.isfinite(a)
    idx = np.where(valid, np.arange(T)[:, None], -1)
    last = np.maximum.accumulate(idx, axis=0)
    gap = np.arange(T)[:, None] - last
    fill = (~valid) & (last >= 0) & (gap <= limit)
    # only fill interior holes: a later valid bar must exist (do not extend a delisted series)
    next_valid = np.flip(np.maximum.accumulate(np.flip(valid, axis=0), axis=0), axis=0)
    fill &= next_valid
    rows, cols = np.nonzero(fill)
    out[rows, cols] = a[last[rows, cols], cols]
    return out
