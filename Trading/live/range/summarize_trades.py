import json
from Trading.model.trade import Trade
from pathlib import Path
from typing import List, Dict
import os

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
TRADES_JSON_PATH = CURRENT_FILE_PATH.joinpath("trades.json")

def load_trades():
    with open(TRADES_JSON_PATH) as f:
        data = json.load(f)
    for i, t in enumerate(data):
        data[i] = Trade(**t)
    return data

def get_total_invested_raw(trades: List[Trade]):
    # This does not take into account reinvesting profits
    total = 0
    for t in trades:
        total += t.volume * t.open_price
    return total

def get_total_profit(trades: List[Trade]):
    total = 0
    for t in trades:
        total += t.profit
    return total

def get_number_of_days_open(trades: List[Trade]):
    earliest_open_date = None
    latest_close_date = None
    for t in trades:
        if earliest_open_date is None or t.entry_date < earliest_open_date:
            earliest_open_date = t.entry_date
        if latest_close_date is None or t.exit_date > latest_close_date:
            latest_close_date = t.exit_date
    if earliest_open_date is None or latest_close_date is None:
        return 0
    from datetime import timedelta, date
    # parse string to date
    earliest_open_date = date.fromisoformat(earliest_open_date)
    latest_close_date = date.fromisoformat(latest_close_date)
    return (latest_close_date - earliest_open_date).days

def get_cagr(trades: List[Trade]):
    total_invested = get_invested_money(trades)
    total_profit = get_total_profit(trades)
    return_rate = total_profit / total_invested
    number_of_days = get_number_of_days_open(trades)
    return return_rate * 365 / number_of_days

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
        if t.entry_date == t.exit_date:
            continue
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

def get_start_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.entry_date)
    return trades[0].entry_date

def get_end_date(trades: List[Trade]):
    trades.sort(key=lambda x: x.exit_date)
    return trades[-1].exit_date

print(f"From {get_start_date(load_trades())} to {get_end_date(load_trades())}")

total_invested = get_invested_money(load_trades())
print(f"Total invested: {round(total_invested, 2)}")
total_profit = get_total_profit(load_trades())
print(f"Total profit: {round(total_profit, 2)}")

return_rate = total_profit / total_invested
print(f"Return rate: {round(return_rate * 100, 2)}%")

n_days = get_number_of_days_open(load_trades())
print(f"Number of days open: {n_days}")
cagr = get_cagr(load_trades()) * 100
cagr = round(cagr, 2)
print(f"CAGR: {cagr}%")
