from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime
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
        # including date
        index = self.date.index(date)
        return self.slice(index-n, index+1)

    def sort_by_dates(self):
        sorted_indices = sorted(range(len(self.date)), key=lambda i: self.date[i])
        self.date = [self.date[i] for i in sorted_indices]
        self.open = [self.open[i] for i in sorted_indices]
        self.high = [self.high[i] for i in sorted_indices]
        self.low = [self.low[i] for i in sorted_indices]
        self.close = [self.close[i] for i in sorted_indices]

    def extend(self, history: 'History'):
        if self.symbol != history.symbol:
            raise ValueError("Cannot extend history with different symbol")
        if self.timeframe != history.timeframe:
            raise ValueError("Cannot extend history with different timeframe")

        self.date.extend(history.date)
        self.open.extend(history.open)
        self.high.extend(history.high)
        self.low.extend(history.low)
        self.close.extend(history.close)

        date_set = set()
        date_index = []
        for i, d in enumerate(self.date):
            if d in date_set:
                date_index.append(i)
            date_set.add(d)
        for i in reversed(date_index):
            self.date.pop(i)
            self.open.pop(i)
            self.high.pop(i)
            self.low.pop(i)
            self.close.pop(i)
        self.sort_by_dates()

    def __getitem__(self, item):
        return getattr(self, item)

class OHLC(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
