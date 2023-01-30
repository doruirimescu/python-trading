from datetime import date
from enum import Enum
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional


class TradeType(Enum):
    BUY = "BUY"
    SHORT = "SHORT"

@dataclass_json
@dataclass
class Trade:
    """Dataclass representing a trade
    """
    date_: date
    type_: TradeType
    contract_value: int
    volume: Optional[int] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    profit: Optional[float] = None
    position_id: Optional[str] = None
