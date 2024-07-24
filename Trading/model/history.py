from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class History(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    date: Optional[List[str]] = None
    open: Optional[List[float]] = None
    high: Optional[List[float]] = None
    low: Optional[List[float]] = None
    close: Optional[List[float]] = None

    def __getitem__(self, item):
        return getattr(self, item)

class OHLC(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
