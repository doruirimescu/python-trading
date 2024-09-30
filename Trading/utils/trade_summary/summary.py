# bring methods that act on lists of trades
from Trading.model.trade import Trade
from typing import List

def get_start_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.entry_date)
    return trades[0].entry_date

def get_end_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.exit_date)
    return trades[-1].exit_date

def get_invested_money(trades: List[Trade]) -> float:
    """Calculate the total input money required to execute a series of trades, considering reinvestment of money obtained
    from closed trades when possible. The input money is calculated as the sum of the money required
    to open a trade, minus the money obtained from closed trades when possible. The money obtained from closed trades is
    calculated as the sum of the volume of the trade times the close price of the trade. The money required to open a trade
    is calculated as the volume of the trade times the open price of the trade. The money obtained from closed trades is
    calculated as the sum of the volume of the trade times the close price of the trade.
    Args:
        trades (List[Trade]): A list of performed trades

    Returns:
        float: The total input money required to execute the trades
    """
    input_money = 0
    money_from_closed_trades = 0
    trades.sort(key=lambda x: x.entry_date)

    # add property visited to trades
    for t in trades:
        t.visited = False

    def get_trades_that_closed_before(trades: List[Trade], date):
        return [t for t in trades if t.exit_date < date and not t.visited]

    for t in trades:
        trades_that_closed_before = get_trades_that_closed_before(trades, t.entry_date)
        for trade in trades_that_closed_before:
            money_from_closed_trades += (trade.volume * trade.close_price)
            trade.visited = True
        money_required = t.volume * t.open_price
        if money_from_closed_trades >= money_required:
            money_from_closed_trades -= money_required
        else:
            input_money += (money_required - money_from_closed_trades)
            money_from_closed_trades = 0

    print(f"Input money: {input_money:.2f}")
    print(f"Money from closed trades: {money_from_closed_trades:.2f}")
    return input_money
