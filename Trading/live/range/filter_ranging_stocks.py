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
from Trading.symbols.constants import (
    XTB_ETF_SYMBOLS,
    XTB_STOCK_SYMBOLS,
    XTB_STOCK_SYMBOLS_DICT,
)
from Trading.model.history import History, OHLC
from Trading.utils.range.range import PerfectRange
from Trading.utils.time import get_date_now_cet
from Trading.utils.custom_logging import get_logger
from Trading.utils.criterion.expression import Threshold, ThresholdLE, ThresholdGE, and_

from Trading.algo.ranker.ranker import RangeScorer, Ordering


LOGGER = get_logger("filter_ranging_stocks")


def exit():
    sys.exit(0)


ORDERING_SIZE = 70

RANGE_WIDTH = 15
RANGE_HEIGHT = 1.1
COMPARISON_LAG = 24
TIMEFRAME = "1M"
PERCENTAGE_WIN = 1.10

range_scorer = RangeScorer(window=RANGE_WIDTH)
range_ordering = Ordering(top_n=ORDERING_SIZE, score_calculator=range_scorer)


class StockRangeProcessor(StatefulDataProcessor):
    def __init__(
        self, json_file_rw, logger, should_reload_ordering=False, should_reprocess=False
    ):
        global range_ordering
        super().__init__(json_file_rw, logger, should_reprocess=should_reprocess)
        # Load range ordering from file
        if (
            should_reload_ordering
            and self.data is not None
            and self.data.get("range_ordering") is not None
        ):
            # If we want to load the previous range ordering from the file, we can do it here
            range_ordering = Ordering(**self.data["range_ordering"])

    def process_item(self, item, iteration_index, client):
        try:
            if "CLOSE ONLY" in XTB_STOCK_SYMBOLS_DICT[item]["description"]:
                return

            # check that the price has not been falling too much over the last 24 months
            history_lag = client.get_last_n_candles_history(
                Instrument(item, Timeframe(TIMEFRAME)), COMPARISON_LAG
            )
            history_lag = History(**history_lag)
            history_lag.symbol = item
            history_lag.timeframe = TIMEFRAME

            history_range = history_lag.slice(-RANGE_WIDTH)
            range_ratio = history_range.get_range_ratio()
            if range_ratio < RANGE_HEIGHT:
                return

            ask = client.get_symbol(item)["ask"]
            if ask is None:
                self.data[item] = None
                return
            else:
                self.data[item] = history_range.dict()
                range_ordering.add_history(history_range)
                self.data["range_ordering"] = range_ordering.model_dump()
                LOGGER.info(range_ordering.scores)
        except Exception as e:
            LOGGER.error(f"Error processing {item}: {e}")
            self.data[item] = None
            return

    def reprocess_item(self, item, iteration_index, client) -> XTB_STOCK_SYMBOLS_DICT:
        # Go through the history and try some new things with the range ordering.
        # This works best if some parameter of the range ordering has changed
        if self.data[item] is None:
            return
        history = History(**self.data[item])
        range_ordering.add_history(history)
        self.data["range_ordering"] = range_ordering.model_dump()
        LOGGER.info(range_ordering.scores)


if __name__ == "__main__":
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    # temp json file storage
    file_path = f"range-scorer-stocks-{get_date_now_cet()}.json"
    js = JsonFileRW(
        RANGING_STOCKS_PATH.joinpath("workfile.json"),
        LOGGER,
    )
    sp = StockRangeProcessor(
        js, LOGGER, should_reload_ordering=True, should_reprocess=False
    )
    LOGGER.info(f"Items length: {len(XTB_STOCK_SYMBOLS)}")
    sp.run(items=XTB_STOCK_SYMBOLS, client=client)

    # Now that we have the perfect range, we can filter the stocks further: we need to have the current price within the range
    # and the current price should be at the low end of the range
    candidates = dict()
    LOGGER.info(range_ordering.scores)
    for item in range_ordering.scores.items():
        hist = History(**sp.data[item[0]]).slice(-RANGE_WIDTH)
        ask = client.get_symbol(item[0])["ask"]
        lowest = hist.calculate_percentile(OHLC.LOW, 20)

        highest = hist.calculate_percentile(OHLC.HIGH, 80)
        potential_win_p = highest / ask
        potential_win_percent = ThresholdGE(name="potential_win_percent", threshold=PERCENTAGE_WIN)
        potential_win_percent.left = potential_win_p

        # conditions = and_(potential_win_percent)
        if potential_win_percent.evaluate():
            candidates[item[0]] = potential_win_p
    candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
    for candidate in candidates:
        LOGGER.info(f"{candidate[0]}: {candidate[1]:.3f}")
