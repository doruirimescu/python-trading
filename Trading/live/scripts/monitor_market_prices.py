from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE, DATA_STORAGE_PATH
from Trading.live.alert.alert import (get_total_swap_of_open_forex_trades_report,
                                     is_symbol_price_below_value,
                                     is_symbol_price_above_value,
                                     is_symbol_price_below_last_n_intervals_low,
                                     is_symbol_price_above_last_n_intervals_low)
from Trading.utils.write_to_file import read_json_file
from Trading.utils.time import get_date_now_cet
from Trading.instrument.instrument import Instrument
from Trading.live.scripts.data.symbols.failing_symbols import FAILING_SYMBOLS

from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from time import sleep

TIMEFRAME_TO_MONITOR = '1M'
N_TIMEFRAMES = 12

PRICES_ABOVE_ALERTS = [('USDHUF', 360), ('EURMXN', 21), ('CHFHUF', 390), ('GOLD', 1950), ('NATGAS', 3), ('MAXR.US', 53), ('PALLADIUM', 1650)]
PRICES_BELOW_ALERTS = [('EBAY.US_9', 39), ('NATGAS', 2), ('ETSY.US_9', 79), ('BABA.US_9', 78), ('CHFHUF', 370), ('MAXR.US', 48), ('PALLADIUM', 1500)]

if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    all_symbols_dict = read_json_file(DATA_STORAGE_PATH + 'symbols/all_symbols.json')
    failing_symbols = list()
    report = "-------CUSTOM ALERTS-------"
    for symbol, price in PRICES_BELOW_ALERTS:
        try:
            r = is_symbol_price_below_value(client, symbol, price)
            if r is not None:
                report += r
                report += "\n"
                MAIN_LOGGER.info(r)
        except Exception as e:
            MAIN_LOGGER.info(str(e) + " " + symbol)
            failing_symbols.append(symbol)

    for symbol, price in PRICES_ABOVE_ALERTS:
        try:
            r = is_symbol_price_above_value(client, symbol, price)
            if r is not None:
                report += r
                report += "\n"
                MAIN_LOGGER.info(r)
        except Exception as e:
            MAIN_LOGGER.info(str(e) + " " + symbol)
            failing_symbols.append(symbol)

    report += "-------MARKET ANALYSIS-------"
    for symbol in all_symbols_dict:
        if symbol in FAILING_SYMBOLS:
            continue
        try:
            r = is_symbol_price_below_last_n_intervals_low(client, Instrument(symbol, TIMEFRAME_TO_MONITOR), N_TIMEFRAMES)
            if r is not None:
                report += r
                report += "\n"
                MAIN_LOGGER.info(r)
        except Exception as e:
            MAIN_LOGGER.info(str(e) + " " + symbol)
            failing_symbols.append(symbol)
        try:
            r = is_symbol_price_above_last_n_intervals_low(client, Instrument(symbol, TIMEFRAME_TO_MONITOR), N_TIMEFRAMES)
            if r is not None:
                report += r
                report += "\n"
                MAIN_LOGGER.info(r)
        except Exception as e:
            MAIN_LOGGER.info(str(e) + " " + symbol)
            failing_symbols.append(symbol)


time_now = str(get_date_now_cet())
subject = "Daily market monitor report " + time_now
report += "\n"
report += str(failing_symbols)
send_email(subject, report)
