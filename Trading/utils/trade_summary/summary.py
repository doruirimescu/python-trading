# bring methods that act on lists of trades
from Trading.model.trade import Trade, BuyTradeOrder, SellTradeOrder
from typing import List

def get_start_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.entry_date)
    return trades[0].entry_date

def get_end_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.exit_date)
    return trades[-1].exit_date

def get_invested_money(trades: List[Trade]) -> float:
    """Calculate the total input money required to execute a series of trades, considering reinvestment of money obtained
    from closed trades when possible.
    Args:
        trades (List[Trade]): A list of performed trades

    Returns:
        float: The total input money required to execute the trades
    """
    orders = [order for t in trades for order in t.get_orders()]
    orders.sort(key=lambda x: x.date)

    input_money, money_from_closed_trades = 0, 0

    for o in orders:
        if isinstance(o, BuyTradeOrder):
            money_needed_to_start_trade = o.price * o.volume
            if money_from_closed_trades >= money_needed_to_start_trade:
                money_from_closed_trades += money_needed_to_start_trade
            else:
                input_money += money_needed_to_start_trade - money_from_closed_trades
                money_from_closed_trades = 0
        else:
            money_from_closed_trades += o.price * o.volume

    print(f"Input money: {input_money:.2f}")
    print(f"Money from closed trades: {money_from_closed_trades:.2f}")
    return input_money
