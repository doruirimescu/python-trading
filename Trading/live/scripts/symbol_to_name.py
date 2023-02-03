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

    all_symbols = client.get_all_symbols()
    print(all_symbols)

    data_dict = dict()
    for s in all_symbols:
        info = client.get_symbol(s)
        symbol = info['symbol']
        data_dict[symbol] = info

        print(s)

    import json
    f = open('data/symbols_to_name.json', 'w')
    json_object = json.dumps(data_dict, indent=4)
    f.write(json_object)
    f.close()
