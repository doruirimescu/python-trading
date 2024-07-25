from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BidAsk(Enum):
    BID = 0
    ASK = 1

    @classmethod
    def from_str(cls, value: str):
        if value == 'BID':
            return cls.BID
        elif value == 'ASK':
            return cls.ASK
        else:
            raise ValueError(f"Invalid BidAsk value: {value}")

class PriceQuote(BaseModel):
    price: float
    time: Optional[datetime] = None
    currency: Optional[str] = None
