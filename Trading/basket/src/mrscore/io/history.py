from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

import numpy as np


class OHLC(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


@dataclass(frozen=True)
class History:
    """
    Performance-oriented time series container.
    - dates: np.datetime64[D] or np.datetime64[ns]
    - fields: float64 arrays of same length
    """
    symbol: str
    dates: np.ndarray
    open: Optional[np.ndarray] = None
    high: Optional[np.ndarray] = None
    low: Optional[np.ndarray] = None
    close: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        # Basic invariants (cheap)
        n = len(self.dates)
        for name in ("open", "high", "low", "close"):
            arr = getattr(self, name)
            if arr is not None and len(arr) != n:
                raise ValueError(f"{name} length must match dates length")

    def field(self, ohlc: OHLC) -> np.ndarray:
        arr = getattr(self, ohlc.value)
        if arr is None:
            raise ValueError(f"Missing field: {ohlc.value}")
        return arr

    def normalize(self, ohlc: OHLC) -> "History":
        x = self.field(ohlc)
        base = float(x[0])
        if base == 0.0:
            raise ValueError("Cannot normalize: first value is zero")
        # Create only the normalized field you need
        norm = x / base
        kwargs = {ohlc.value: norm}
        return History(symbol=self.symbol, dates=self.dates, **kwargs)
