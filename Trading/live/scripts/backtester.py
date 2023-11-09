from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument.instrument import Instrument
from dotenv import load_dotenv
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT, XTB_INDEX_SYMBOLS_DICT, XTB_ETF_SYMBOLS_DICT
import os
import logging
import sys
import Trading.algo.strategy.rsi_strategy as strategy_under_test
from Trading.utils.timeseries import slice_data_np
import Trading.utils.visualize as visualize
from typing import List
import numpy as np
from datetime import date


def exit():
    sys.exit(0)



SYMBOLS_TO_TEST = ['TUR.US_5', 'US500']

def setup_parameters():
    N_DAYS = 2000
    SHOULD_REINVEST = True
    DESIRED_CASH_INVESTED = 1000
    PRINT_ANNUALIZED_RETURNS = False

    return (N_DAYS, SHOULD_REINVEST, DESIRED_CASH_INVESTED, PRINT_ANNUALIZED_RETURNS)

def n_days():
    (N_DAYS, _, _, _) = setup_parameters()
    return N_DAYS

def analyze_trades(trades: List[strategy_under_test.Trade], symbol: str, history):
    (N_DAYS, SHOULD_REINVEST, DESIRED_CASH_INVESTED, PRINT_ANNUALIZED_RETURNS) = setup_parameters()
    symbol_info = XTB_ALL_SYMBOLS_DICT[symbol]
    CONTRACT_SIZE = symbol_info['contractSize']
    PROFIT_CURRENCY = symbol_info['currencyProfit']
    CATEGORY_NAME = symbol_info['categoryName']

    total_net_profit = 0
    total_cash_invested = 0
    max_drawdown = 1000000
    max_loss = max_drawdown
    n_profit_trades = 0
    n_loss_trades = 0
    total_loss = 0
    total_profit = 0
    profits_list = []
    average_trade_duration_days = 0
    for t in trades:
        t.calculate_max_drawdown_price_diff(history)
        average_trade_duration_days += t.duration_days()
        if SHOULD_REINVEST:
            cash_to_invest = DESIRED_CASH_INVESTED + total_profit
        else:
            cash_to_invest = DESIRED_CASH_INVESTED

        volume = (cash_to_invest)/(t.open_price * CONTRACT_SIZE)

        if CATEGORY_NAME == 'IND':
            volume = round(volume, 2)
            volume = max(0.01, volume)
        elif CATEGORY_NAME == 'ETF':
            volume = int(volume)

        actual_cash_invested = volume * t.open_price * CONTRACT_SIZE
        p = CONTRACT_SIZE * volume * (t.close_price - t.open_price)

        total_cash_invested += actual_cash_invested

        if p < max_loss:
            max_loss = p
        total_net_profit += p
        max_drawdown = min(max_drawdown, t.max_drawdown.value)
        profits_list.append(total_net_profit)
        if p < 0:
            n_loss_trades += 1
            total_loss += p
        else:
            n_profit_trades += 1
            total_profit += p
    average_cash_per_trade = total_cash_invested/len(trades)
    average_trade_duration_days = average_trade_duration_days/len(trades)

    print(f"Total net profit: {total_net_profit:.2f} {PROFIT_CURRENCY}")
    print(f"Average cash invested per trade: {average_cash_per_trade:.2f} {PROFIT_CURRENCY}")
    for t in trades:
        if t.max_drawdown.value == max_drawdown:
            entry_date = t.entry_date.date()
            drawdown_date = t.max_drawdown.date.date()
            print(f"Max drawdown {max_drawdown:.2f} {PROFIT_CURRENCY} between {entry_date} and {drawdown_date}")

    print(f"A number of {len(trades)} trades were made during {N_DAYS} days")
    print(f"Profit trades: {n_profit_trades}, Loss trades: {n_loss_trades} Win ratio: {100*n_profit_trades/len(trades):.2f}%")
    print(f"Reward to risk ratio: {abs(total_profit/total_loss):.2f}")
    print(f"Average trade duration: {average_trade_duration_days:.2f} days")

    n_years = N_DAYS/365.0

    annualized_return = ((total_net_profit + average_cash_per_trade)/average_cash_per_trade) **(1/n_years) - 1
    print(f"Annualized returns: {100*annualized_return:.2f}%")
    if 100*annualized_return > 10.0:
        symbol_to_annualized_returns[symbol] = 100*annualized_return

    if PRINT_ANNUALIZED_RETURNS:
        print(symbol_to_annualized_returns)

if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger("Main logger")
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    N_DAYS = n_days()
    symbol_to_annualized_returns = dict()
    all_trades = list()

    for symbol in SYMBOLS_TO_TEST:
        print("--------------------------------------------------")
        print(f"Dealing with {symbol}...")

        try:
            history = client.get_last_n_candles_history(Instrument(symbol, "1D"), N_DAYS)

        except Exception as e:
            print(f"Failed to get history for {symbol}")
            continue

        trade_entry_dates = []
        for i in range(5, N_DAYS + 1):
            data = slice_data_np(history, i)
            if strategy_under_test.should_enter_trade(data):
                trade_entry_dates.append(history['date'][i])

        trades = strategy_under_test.get_trades(data, trade_entry_dates)
        all_trades.append(trades)
        for t in trades:
            t.symbol = symbol
        analyze_trades(trades, symbol, history)

    visualize.plot_trades_gant(all_trades)
    #strategy_under_test.plot_data(history_days)
