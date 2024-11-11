import logging
import os
import sys

from dotenv import load_dotenv
from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

from Trading.config.config import MODE, PASSWORD, RANGING_STOCKS_PATH, USERNAME
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.live.client.client import XTBTradingClient
from Trading.symbols.constants import XTB_ETF_SYMBOLS, XTB_STOCK_SYMBOLS, XTB_STOCK_SYMBOLS_DICT
from Trading.model.history import History
from Trading.utils.range.range import PerfectRange
from Trading.utils.time import get_date_now_cet
from Trading.utils.custom_logging import get_logger
from Trading.utils.criterion.expression import Threshold, ThresholdLE

from Trading.algo.ranker.ranker import RangeScorer, Ordering


LOGGER = get_logger("filter_ranging_stocks")

def exit():
    sys.exit(0)

TOP = 30

RANGE_WIDTH = 15
TOLERANCE = None#0.05 # how much above the low the current price can be
RANGE_HEIGHT = 1.1
COMPARISON_LAG = 24
TIMEFRAME = '1M'
perfect_range = PerfectRange(RANGE_WIDTH, TOP, TOLERANCE)

range_scorer = RangeScorer(window=RANGE_WIDTH)
range_ordering = Ordering(top_n=TOP, score_calculator=range_scorer)

class StockRangeProcessor(StatefulDataProcessor):

    def __init__(self, json_file_rw, logger):
        global range_ordering
        super().__init__(json_file_rw, logger)
        # Load range ordering from file
        if self.data is not None and self.data.get('range_ordering') is not None:
            # load pydantic
            range_ordering = Ordering(**self.data['range_ordering'])

    def process_item(self, item, iteration_index, client):
        global perfect_range, N_MONTHS
        try:
            if "CLOSE ONLY" in XTB_STOCK_SYMBOLS_DICT[item]["description"]:
                return

            # check that the price has not been falling too much over the last 24 months
            history_lag = client.get_last_n_candles_history(Instrument(item, Timeframe(TIMEFRAME)), COMPARISON_LAG)
            history_lag = History(**history_lag)
            history_lag.symbol = item
            history_lag.timeframe = TIMEFRAME

            current_price_less_than_lag = ThresholdLE("Current price is less than point 24 months ago", history_lag.close[0])
            current_price_less_than_lag.value = history_lag.close[-1]
            current_price_less_than_lag.disable()

            # if current_price_less_than_lag.evaluate():
            #     return

            history_range = history_lag.slice(-RANGE_WIDTH)

            ask = client.get_symbol(item)["ask"]
            if ask is None:
                self.data[item] = None
                return
            else:
                # perfect_range.add_history(history_range, ask, range_height=RANGE_HEIGHT)
                self.data[item] = history_range.dict()
                range_ordering.add_history(history_range)
                self.data['range_ordering'] = range_ordering.model_dump()
                LOGGER.info(range_ordering.scores)
        except Exception as e:
            LOGGER.error(f"Error processing {item}: {e}")
            self.data[item] = None
            return

if __name__ == '__main__':
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    # temp json file storage
    js = JsonFileRW(RANGING_STOCKS_PATH.joinpath(f"range-scorer-stocks-{get_date_now_cet()}.json"), LOGGER)
    sp = StockRangeProcessor(js, LOGGER)
    LOGGER.info(f"Items length: {len(XTB_STOCK_SYMBOLS)}")
    sp.run(items=XTB_STOCK_SYMBOLS, client=client)

# GREAT FINDS:
# FIZZ.US_9 BTU.US!, BHF.US?
