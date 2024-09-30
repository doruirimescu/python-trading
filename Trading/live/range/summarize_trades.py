import json
from Trading.model.trade import Trade
from Trading.utils.trade_summary.summary import (
    get_start_date,
    get_end_date,
    get_invested_money,
)
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
