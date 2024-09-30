# bring methods that act on lists of trades
from Trading.model.trade import Trade
from typing import List

def get_start_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.entry_date)
    return trades[0].entry_date

def get_end_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.exit_date)
    return trades[-1].exit_date
