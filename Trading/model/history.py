from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime
from bisect import bisect_left

class History(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    date: Optional[List[datetime]] = None
    open: Optional[List[float]] = None
    high: Optional[List[float]] = None
    low: Optional[List[float]] = None
    close: Optional[List[float]] = None

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
            close=self.close[start:end]
        )

    def slice_n_candles_before_date(self, date: str, n: int):
        # Use bisect_left to find the index efficiently
        index = bisect_left(self.date, date)
        return self.slice(max(0, index-n), index+1)

    def sort_by_dates(self) -> None:
        # Zip the data together and sort by dates
        combined = list(zip(self.date, self.open, self.high, self.low, self.close))
        combined.sort(key=lambda x: x[0])
        # Unzip sorted data
        self.date, self.open, self.high, self.low, self.close = map(list, zip(*combined))


    def extend(self, history: 'History'):
        if self.symbol != history.symbol:
            raise ValueError(f"Cannot extend history {self.symbol} with different symbol {history.symbol}")
        if self.timeframe != history.timeframe:
            raise ValueError(f"Cannot extend history {self.timeframe} with different timeframe {history.timeframe}")

        self.date.extend(history.date)
        self.open.extend(history.open)
        self.high.extend(history.high)
        self.low.extend(history.low)
        self.close.extend(history.close)

        # Remove duplicates and sort by date in a single pass
        combined = list(zip(self.date, self.open, self.high, self.low, self.close))
        combined = sorted(set(combined), key=lambda x: x[0])  # Remove duplicates and sort by date
        self.date, self.open, self.high, self.low, self.close = map(list, zip(*combined))

    def __getitem__(self, item):
        return getattr(self, item)
    def __len__(self):
        return len(self.date)
class OHLC(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
