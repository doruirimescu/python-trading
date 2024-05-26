from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument, Timeframe
from Trading.symbols.constants import XTB_STOCK_SYMBOLS, XTB_ETF_SYMBOLS
from Trading.utils.range.range import PerfectRange
from Trading.utils.history import History
from Trading.utils.data_processor import DataProcessor, JsonFileRW
from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url, get_alphaspread_url_from_ticker
from dotenv import load_dotenv
import os
import logging
import sys

def exit():
    sys.exit(0)

N_MONTHS = 20
TOP = 20
TOLERANCE = 0.05 # how much above the low the current price can be
perfect_range = PerfectRange(N_MONTHS, TOP, TOLERANCE)


class StockRangeProcessor(DataProcessor):
    def _process_data(self, items, client):
        self.iterate_items(items, client=client)

    def process_item(self, item, client):
        global perfect_range, N_MONTHS
        # remove anything after . from string

        # if not perfect_range.ranks and len(self.data) > 1:
        #     for item, history in self.data.items():
        #         if history is None:
        #             continue
        #         ask = client.get_symbol(item)["ask"]
        #         perfect_range.add_history(History(**history), ask)
        try:
            history_months = client.get_last_n_candles_history(Instrument(item, Timeframe('1M')), N_MONTHS)
            history_months['date'] = [str(d.date()) for d in history_months['date']]
            history = History(**history_months)
            history.symbol = item
            history.timeframe = '1M'

            ask = client.get_symbol(item)["ask"]
            if ask is None:
                self.data[item] = None
                return
            else:
                perfect_range.add_history(history, ask)
                self.data[item] = history.dict()
        except Exception as e:
            self.data[item] = None
            return

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

    # temp json file storage
    js = JsonFileRW('temp_all_etf.json', MAIN_LOGGER)
    sp = StockRangeProcessor(js, MAIN_LOGGER)
    sp.run(items=XTB_ETF_SYMBOLS, client=client)

# GREAT FINDS:
# FIZZ.US_9 BTU.US!, BHF.US?
