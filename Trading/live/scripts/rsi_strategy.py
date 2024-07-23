from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from dotenv import load_dotenv
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT, XTB_INDEX_SYMBOLS, XTB_ETF_SYMBOLS
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

FOUND_PROFITABLE_SYMBOLS = ['CH50cash', 'US100', 'SOXX.US_5', 'IBB.US_5', 'TUR.US_5', 'TQQQ.US_5', 'SSO.US_5',
                            'SOXL.US_5', 'ITKY.NL', 'QLD.US_5', 'XME.US_5', 'ITB.US_5']

SYMBOLS_TO_TEST = FOUND_PROFITABLE_SYMBOLS
# SYMBOLS_TO_TEST.extend(XTB_INDEX_SYMBOLS)
# SYMBOLS_TO_TEST.extend(XTB_ETF_SYMBOLS)

def setup_parameters():
    N_DAYS = 2000
    SHOULD_REINVEST = True
    DESIRED_CASH_INVESTED = 1000
    PRINT_ANNUALIZED_RETURNS = False

    return (N_DAYS, SHOULD_REINVEST, DESIRED_CASH_INVESTED, PRINT_ANNUALIZED_RETURNS)

def n_days():
    (N_DAYS, _, _, _) = setup_parameters()
    return N_DAYS

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
            history = client.get_last_n_candles_history(Instrument(symbol, Timeframe("1D")), N_DAYS)

        except Exception as e:
            print(f"Failed to get history for {symbol}")
            continue

        trade_entry_dates = []
        print(history['date'][-1])
        data = slice_data_np(history, len(history['date']))
        print(data['date'][-1])
        if strategy_under_test.should_enter_trade(data):
            print(f"Should enter trade for {symbol}")
