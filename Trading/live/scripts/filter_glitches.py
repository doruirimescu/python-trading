from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import (get_date_now_cet,
                                get_datetime_now_cet,
                                get_seconds_to_next_date)
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.trade.trade import TradeType, Trade
from Trading.instrument import Instrument, Timeframe
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

profitable_symbols_dict = read_json_file('profitable_symbols/2023-01-29')
output = profitable_symbols_dict.copy()
SYMBOLS = profitable_symbols_dict.keys()
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

    for symbol in SYMBOLS:
        day_hist = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), 100)
        count = 0
        for o, l in zip(day_hist['open'], day_hist['low']):
            if o == l:
                count += 1
        if count > 30:
            del output[symbol]
        print(symbol, count)
    print(output)

    # import json
    # f = open('data/filtered_glitches.json', 'w')
    # json_object = json.dumps(output, indent=4)
    # f.write(json_object)
    # f.close()
