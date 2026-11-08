"""Per-ticker on-disk cache (compressed npz, atomic writes), in the spirit of mrscore.io.cache.

One file per (source, ticker): ``<root>/<source>/<TICKER>.npz`` holding the full adjusted close history
plus when it was fetched and how many years were requested. A miss (ticker yfinance does not know) is
cached too, so dead tickers are not re-requested on every run.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class CachedSeries:
    dates: np.ndarray       # datetime64[D]
    close: np.ndarray       # float64
    fetched_on: date
    years: float

    @property
    def empty(self) -> bool:
        return len(self.dates) == 0


def _slug(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9._^=-]+", "_", ticker)


class SeriesCache:
    def __init__(self, root: str | Path, source: str):
        self.dir = Path(root).expanduser() / source
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, ticker: str) -> Path:
        return self.dir / f"{_slug(ticker)}.npz"

    def get(self, ticker: str) -> Optional[CachedSeries]:
        p = self.path(ticker)
        if not p.exists():
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                return CachedSeries(
                    dates=np.asarray(z["dates"], dtype="datetime64[D]"),
                    close=np.asarray(z["close"], dtype=np.float64),
                    fetched_on=date.fromisoformat(str(z["fetched_on"][0])),
                    years=float(z["years"][0]),
                )
        except Exception:
            return None  # corrupt file -> treat as a miss and overwrite

    def put(self, ticker: str, dates: np.ndarray, close: np.ndarray, *, fetched_on: date, years: float) -> None:
        p = self.path(ticker)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(
            tmp,
            dates=np.asarray(dates, dtype="datetime64[D]"),
            close=np.asarray(close, dtype=np.float64),
            fetched_on=np.array([fetched_on.isoformat()]),
            years=np.array([years], dtype=np.float64),
        )
        os.replace(tmp, p)

    @staticmethod
    def is_fresh(entry: CachedSeries, *, today: date, end: Optional[date], years: float, max_age_days: int) -> bool:
        if entry.years + 1e-9 < years:
            return False
        if end is not None and entry.fetched_on > end:
            return True  # history up to a past end date does not change
        return (today - entry.fetched_on).days < max_age_days if max_age_days > 0 else False
