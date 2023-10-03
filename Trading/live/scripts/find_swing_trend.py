from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE, ETF_PATH

from Trading.utils.write_to_file import read_json_file
from Trading.utils.time import get_date_now_cet
from Trading.instrument.instrument import Instrument
from Trading.live.scripts.data.symbols.failing_symbols import FAILING_SYMBOLS
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from time import sleep

TIMEFRAME = '1M'
N_CANDLES = 24

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

    # read etf symbols
    etf_symbols = read_json_file(ETF_PATH)
    etf_instruments = [Instrument(symbol, TIMEFRAME) for symbol in etf_symbols]

    for etf_instrument in etf_instruments:
        try:
            day_hist = client.get_last_n_candles_history(etf_instrument, N_CANDLES)
        except Exception as e:
            continue
        max_price = max(day_hist['high'])
        min_price = min(day_hist['low'])
        box_width = max_price - min_price

        average_high = sum(day_hist['high']) / len(day_hist['high'])
        average_low = sum(day_hist['low']) / len(day_hist['low'])
        average_width = average_high - average_low

        box_fit_p = average_width / box_width
        box_fit_p = round(box_fit_p, 2)

        if box_fit_p >= 0.3:
            print("+++++ FOUND WINNER +++++", etf_instrument.symbol, box_fit_p)
        else:
            print("FOUND LOSER", etf_instrument.symbol, box_fit_p)
