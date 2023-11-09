
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Trade:
    cmd: int #0 buy, 1 sell
    entry_date: datetime
    exit_date: datetime
    open_price: float
    close_price: float
