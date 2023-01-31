from datetime import date
from enum import Enum
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional

@dataclass_json
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

    def get_dict(self):
        return {'date': str(self.date_), 'type': str(self.type_), 'contract_value': self.contract_value,
                'volume': self.volume, 'open_price': self.open_price, 'close_price': self.close_price,
                'profit': self.profit, 'position_id': self.position_id}
