from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BidAsk(Enum):
    BID = 0
    ASK = 1

class PriceQuote(BaseModel):
    price: float
    time: Optional[datetime] = None
    bid_ask: Optional[BidAsk] = None
