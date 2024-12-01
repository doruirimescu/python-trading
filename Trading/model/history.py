from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from enum import Enum
from datetime import datetime
from bisect import bisect_left
import numpy as np


class OHLC(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


class History(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    date: Optional[List[datetime]] = None
    open: Optional[List[float]] = None
    high: Optional[List[float]] = None
    low: Optional[List[float]] = None
    close: Optional[List[float]] = None
    len: Optional[int] = None

    open_np: Optional[np.ndarray] | Any = None
    high_np: Optional[np.ndarray] | Any = None
    low_np: Optional[np.ndarray] | Any = None
    close_np: Optional[np.ndarray] | Any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
    # post init
    def model_post_init(self, __context):
        self.to_numpy()
        self.len = len(self.date)

    def get_range_ratio(self):
        return self.high_np.max() / self.low_np.min()

    def to_numpy(self):
        self.open_np = np.array(self.open)
        self.high_np = np.array(self.high)
        self.low_np = np.array(self.low)
        self.close_np = np.array(self.close)

    def calculate_mean(self, ohlc: OHLC):
        if ohlc == OHLC.OPEN:
            return self.open_np.mean()
        elif ohlc == OHLC.HIGH:
            return self.high_np.mean()
        elif ohlc == OHLC.LOW:
            return self.low_np.mean()
        elif ohlc == OHLC.CLOSE:
            return self.close_np.mean()

    def calculate_std(self, ohlc: OHLC):
        if ohlc == OHLC.OPEN:
            return self.open_np.std()
        elif ohlc == OHLC.HIGH:
            return self.high_np.std()
        elif ohlc == OHLC.LOW:
            return self.low_np.std()
        elif ohlc == OHLC.CLOSE:
            return self.close_np.std()

    def get_lowest(self, ohlc: OHLC):
        if ohlc == OHLC.OPEN:
            return self.open_np.min()
        elif ohlc == OHLC.HIGH:
            return self.high_np.min()
        elif ohlc == OHLC.LOW:
            return self.low_np.min()
        elif ohlc == OHLC.CLOSE:
            return self.close_np.min()

    def get_highest(self, ohlc: OHLC):
        if ohlc == OHLC.OPEN:
            return self.open_np.max()
        elif ohlc == OHLC.HIGH:
            return self.high_np.max()
        elif ohlc == OHLC.LOW:
            return self.low_np.max()
        elif ohlc == OHLC.CLOSE:
            return self.close_np.max()

    def get_last(self, ohlc: OHLC):
        if ohlc == OHLC.OPEN:
            return self.open_np[-1]
        elif ohlc == OHLC.HIGH:
            return self.high_np[-1]
        elif ohlc == OHLC.LOW:
            return self.low_np[-1]
        elif ohlc == OHLC.CLOSE:
            return self.close_np[-1]

    def calculate_percentile(self, ohlc: OHLC, percentile: float):
        if ohlc == OHLC.OPEN:
            return np.percentile(self.open_np, percentile)
        elif ohlc == OHLC.HIGH:
            return np.percentile(self.high_np, percentile)
        elif ohlc == OHLC.LOW:
            return np.percentile(self.low_np, percentile)
        elif ohlc == OHLC.CLOSE:
            return np.percentile(self.close_np, percentile)

    def slice(self, start: int, end: Optional[int] = None):
        if end is None:
            end = len(self.date)

        return History(
            symbol=self.symbol,
            timeframe=self.timeframe,
            date=self.date[start:end],
            open=self.open[start:end],
            high=self.high[start:end],
            low=self.low[start:end],
            close=self.close[start:end],
        )

    def slice_n_candles_before_date(self, date: str, n: int):
        # Use bisect_left to find the index efficiently
        index = bisect_left(self.date, date)
        return self.slice(max(0, index - n), index + 1)

    def sort_by_dates(self) -> None:
        # Zip the data together and sort by dates
        combined = list(zip(self.date, self.open, self.high, self.low, self.close))
        combined.sort(key=lambda x: x[0])
        # Unzip sorted data
        self.date, self.open, self.high, self.low, self.close = map(
            list, zip(*combined)
        )

    def extend(self, history: "History"):
        if self.symbol != history.symbol:
            raise ValueError(
                f"Cannot extend history {self.symbol} with different symbol {history.symbol}"
            )
        if self.timeframe != history.timeframe:
            raise ValueError(
                f"Cannot extend history {self.timeframe} with different timeframe {history.timeframe}"
            )

        self.date.extend(history.date)
        self.open.extend(history.open)
        self.high.extend(history.high)
        self.low.extend(history.low)
        self.close.extend(history.close)

        # Remove duplicates and sort by date in a single pass
        combined = list(zip(self.date, self.open, self.high, self.low, self.close))
        combined = sorted(
            set(combined), key=lambda x: x[0]
        )  # Remove duplicates and sort by date
        self.date, self.open, self.high, self.low, self.close = map(
            list, zip(*combined)
        )

    def __getitem__(self, item):
        return getattr(self, item)

    def __len__(self):
        return len(self.date)
