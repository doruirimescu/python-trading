from datetime import date
from enum import Enum


class TradeType(Enum):
    BUY = "BUY"
    SHORT = "SHORT"

@dataclass
class Trade:
    """Dataclass representing a trade
    """
    date_: date
    type_: TradeType
    open_price: float
    close_price: float
    profit: float
    volume: int
    position_id: str
