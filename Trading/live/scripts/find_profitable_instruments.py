from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import (get_date_now_cet,
                                get_datetime_now_cet,
                                get_seconds_to_next_date)
from Trading.algo.technical_analyzer.technical_analyzer import DailyBuyTechnicalAnalyzer
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.trade.trade import TradeType, Trade
from Trading.instrument.instrument import Instrument
from Trading.utils.write_to_file import (write_json_to_file_named_with_today_date,
                                        read_json_from_file_named_with_today_date,
                                        read_json_file)
from Trading.utils.argument_parser import CustomParser

from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import round_to_two_decimals, calculate_mean_take_profit, calculate_weighted_mean_take_profit
from typing import List, Tuple, Callable
import logging
import time
import sys


def find_profitable_instruments(client: XTBTradingClient, interval: str, last_n: int, take_profit_percentage: float = 0.1,
                                total_successful_periods_percentage: float = 0.49):
    """Go through all the symbols,

    Args:
        last_n (int): _description_
        take_profit_percentage (float, optional): _description_. Defaults to 0.1.
        total_successful_periods_percentage (float, optional): _description_. Defaults to 0.49.
    """
    symbols = client.get_all_symbols()
    json_dict = read_json_from_file_named_with_today_date("profitable_symbols/")
    for symbol in symbols:
        if "_9" not in symbol:
            continue
        try:
            history = client.get_last_n_candles_history(Instrument(symbol, interval), last_n)
            if history is None:
                continue
        except Exception as e:
            continue
        print(f"Investigating symbol: {symbol}")
        open_high = list(zip(history['open'], history['high']))
        total = 0
        for (open_price, high_price) in open_high:
            if high_price/open_price - 1.0 >= take_profit_percentage:
                total += 1
        if total/last_n > total_successful_periods_percentage:
            if json_dict is None:
                json_dict = dict()
            if not json_dict.get(str(symbol)):
                json_dict[str(symbol)] = dict()
            json_dict[str(symbol)][str(last_n)] = {'period': interval,'take_profit_percentage': take_profit_percentage, 'total_successful_periods': total}
            print("Success", symbol, total/last_n)
        else:
            print("Failure.")
    write_json_to_file_named_with_today_date(json_dict, "profitable_symbols/")



if __name__ == '__main__':
    start_time = get_datetime_now_cet()
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    if "real" == MODE:
        print("Trading with a live client. Do you wish to continue ? y/n")
        should_continue = input().strip()
        if should_continue.lower() != "y":
            sys.exit(0)

    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    find_profitable_instruments(client, '1W', 50, 0.1, 0.4)
