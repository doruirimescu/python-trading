from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument.instrument import Instrument
from dotenv import load_dotenv
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT, XTB_INDEX_SYMBOLS_DICT, XTB_ETF_SYMBOLS_DICT
import os
import logging
import sys
import Trading.algo.strategy.rsi_strategy as strategy_under_test
from typing import List
import numpy as np

def exit():
    sys.exit(0)

SYMBOLS_TO_TEST = ['TUR.US_5']

def setup_parameters():
    N_DAYS = 2000
    SHOULD_REINVEST = True
    DESIRED_CASH_INVESTED = 1000
    PRINT_ANNUALIZED_RETURNS = True

    return (N_DAYS, SHOULD_REINVEST, DESIRED_CASH_INVESTED, PRINT_ANNUALIZED_RETURNS)

def n_days():
    (N_DAYS, _, _, _) = setup_parameters()
    return N_DAYS

def analyze_trades(trades: List[strategy_under_test.Trade], symbol: str):
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
    for t in trades:
        if SHOULD_REINVEST:
            cash_to_invest = DESIRED_CASH_INVESTED + total_profit
        else:
            cash_to_invest = DESIRED_CASH_INVESTED

        if CATEGORY_NAME == 'IND':
            volume = (cash_to_invest)/(t.open_price * CONTRACT_SIZE)
            volume = round(volume, 2)
            volume = max(0.01, volume)

            actual_cash_invested = volume * t.open_price * CONTRACT_SIZE
            p = CONTRACT_SIZE * volume * (t.close_price - t.open_price)

        if CATEGORY_NAME == 'ETF':
            volume = (cash_to_invest) / (t.open_price * CONTRACT_SIZE)
            volume = int(volume)
            actual_cash_invested = volume * t.open_price * CONTRACT_SIZE
            p = volume * (t.close_price - t.open_price)

        total_cash_invested += actual_cash_invested

        if p < max_loss:
            max_loss = p
        total_net_profit += p
        max_drawdown = min(max_drawdown, total_net_profit)
        profits_list.append(total_net_profit)
        if p < 0:
            n_loss_trades += 1
            total_loss += p
        else:
            n_profit_trades += 1
            total_profit += p
    average_cash_per_trade = total_cash_invested/len(trades)

    print(f"Total net profit: {total_net_profit:.2f} {PROFIT_CURRENCY}")
    print(f"Average cash invested per trade: {average_cash_per_trade:.2f} {PROFIT_CURRENCY}")
    print(f"Max drawdown: {max_drawdown:.2f} {PROFIT_CURRENCY} Max loss: {max_loss:.2f} {PROFIT_CURRENCY}")
    print(f"A number of {len(trades)} trades were made during {N_DAYS} days")
    print(f"Profit trades: {n_profit_trades}, Loss trades: {n_loss_trades} Win ratio: {100*n_profit_trades/len(trades):.2f}%")
    print(f"Reward to risk ratio: {abs(total_profit/total_loss):.2f}")

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
    for symbol in SYMBOLS_TO_TEST:
        print("--------------------------------------------------")
        print(f"Dealing with {symbol}...")

        try:
            history_days = client.get_last_n_candles_history(Instrument(symbol, "1D"), N_DAYS)
        except Exception as e:
            print(f"Failed to get history for {symbol}")
            continue

        # arrange data
        history_days['open'] = np.array(history_days['open'], dtype=float)
        history_days['high'] = np.array(history_days['high'], dtype=float)
        history_days['low'] = np.array(history_days['low'], dtype=float)
        history_days['close'] = np.array(history_days['close'], dtype=float)

        open_trade_dates = []
        for i in range(5, N_DAYS):
            data=dict()
            data['open'] = history_days['open'][0:i]
            data['high'] = history_days['high'][0:i]
            data['low'] = history_days['low'][0:i]
            data['close'] = history_days['close'][0:i]
            data['date'] = history_days['date'][0:i]

            if strategy_under_test.should_enter_trade(data):
                open_trade_dates.append(history_days['date'][i])

        trades = strategy_under_test.get_trades(history_days, open_trade_dates)
        analyze_trades(trades, symbol)

    #strategy_under_test.plot_data(history_days)
