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

from Trading.algo.ranker.ranker import RangeScorer, RangeCoherenceMetric, Ordering


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
range_coherence = RangeCoherenceMetric(window=RANGE_WIDTH)
# range_ordering = Ordering(top_n=ORDERING_SIZE, score_calculator=range_scorer)
range_ordering = Ordering(top_n=ORDERING_SIZE, score_calculator=range_coherence)

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
        RANGING_STOCKS_PATH.joinpath(file_path),
        LOGGER,
    )
    sp = StockRangeProcessor(
        js, LOGGER, should_reload_ordering=False, should_reprocess=False
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


# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - STRO.US: 2.467
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - OERL.CH_9: 1.427
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - JAMF.US: 1.318
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - BTG.US: 1.309
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - HLX.US: 1.305
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - FMC.US_9: 1.297
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - DOM.ES_9: 1.295
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - GXO.US_9: 1.286
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - GRE.ES: 1.282
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - NNDM.US: 1.278
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - XWEL.US: 1.256
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - LASR.US_9: 1.250
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - LGIH.US_9: 1.249
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - IAC.US_9: 1.241
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - ELK.NO: 1.237
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - MRK.DE_9: 1.226
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - ANIP.US: 1.221
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - MLKN.US_9: 1.220
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - STR1.US: 1.220
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - LXS.DE_9: 1.206
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - RCUS.US_9: 1.182
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - SNPS.US_9: 1.178
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - ELC.IT: 1.159
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - EPC.US_9: 1.146
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - VITB.SE: 1.143
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - STE.US_9: 1.143
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - PCH.US_9: 1.137
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - RE.US_9: 1.136
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - TTC.US_9: 1.134
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - DRW8.DE_9: 1.133
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - FIZZ.US_9: 1.131
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - PSG.ES_9: 1.130
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - LCII.US_9: 1.130
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - DRW8.DE_4: 1.128
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - ARYN.CH_9: 1.128
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - HAE.US: 1.127
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - BSY.US: 1.123
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - JUP.UK_9: 1.119
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - JCQ.FR_9: 1.109
# 2024-12-17 14:42:28 - INFO - filter_ranging_stocks - ALD.FR_9: 1.101
