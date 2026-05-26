import sys

from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

from Trading.config.config import RANGING_STOCKS_PATH
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.live.client.client import YFinanceLoggingClient
from Trading.symbols.constants import (YAHOO_STOCK_SYMBOLS,
                                       YAHOO_FTSE_ALL_WORLD_SYMBOLS,
                                       YAHOO_SWITZERLAND_SYMBOLS)
from Trading.model.history import History, OHLC
from Trading.utils.time import get_date_now_cet
from Trading.utils.custom_logging import get_logger
from Trading.utils.criterion.expression import Threshold, ThresholdLE, ThresholdGE, and_

from Trading.algo.ranker.ranker import RangeScorer, RangeCoherenceMetric, RobustRangeScorer, Ordering


LOGGER = get_logger("filter_ranging_stocks")


def exit():
    sys.exit(0)


ORDERING_SIZE = 70

RANGE_WIDTH = 15
RANGE_HEIGHT = 1.1
COMPARISON_LAG = 24
TIMEFRAME = "1mo"
PERCENTAGE_WIN = 1.10

range_scorer = RangeScorer(window=RANGE_WIDTH)
range_coherence = RangeCoherenceMetric(window=RANGE_WIDTH)
range_robust_scorer = RobustRangeScorer(window=RANGE_WIDTH)
range_ordering = Ordering(top_n=ORDERING_SIZE, score_calculator=range_coherence)

class StockRangeProcessor(StatefulDataProcessor):
    def __init__(
        self, json_file_rw, logger, should_reload_ordering=False, should_reprocess=False

    ):
        global range_ordering
        super().__init__(json_file_rw, logger, should_reprocess=should_reprocess, verbose_skip=False)
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
            # check that the price has not been falling too much over the last 24 months
            instrument = Instrument(item, Timeframe(TIMEFRAME, client_type="yfinance"))
            history_lag = client.get_last_n_candles_history(instrument, COMPARISON_LAG
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

    def reprocess_item(self, item, iteration_index, client):
        # Go through the history and try some new things with the range ordering.
        # This works best if some parameter of the range ordering has changed
        if self.data[item] is None:
            return
        if ".KS" in item or ".TW" in item or ".HK" in item:
            return
        #If before the first . we have only digits, skip
        if item.split(".")[0].isdigit():
            return
        history = History(**self.data[item])
        range_ordering.add_history(history)
        self.data["range_ordering"] = range_ordering.model_dump()
        #LOGGER.info(range_ordering.scores)


if __name__ == "__main__":
    client = YFinanceLoggingClient()

    # temp json file storage
    file_path = f"range-scorer-stocks-switzerland.json"
    js = JsonFileRW(
        RANGING_STOCKS_PATH.joinpath(file_path),
        LOGGER,
    )
    sp = StockRangeProcessor(
        js, LOGGER, should_reload_ordering=False, should_reprocess=True
    )
    symbols = YAHOO_SWITZERLAND_SYMBOLS
    LOGGER.info(f"Items length: {len(symbols)}")
    sp.run(items=symbols, client=client)

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

# 20.05.2025 Coherence metric for the top 70 stocks:
# WOOF.US_9: 1.597
# GTN.US_9: 1.513
# BILL.US_9: 1.472
# ASC.UK_9: 1.470
# GLBE.US_9: 1.457
# CRNC.US_9: 1.428
# CYH.US_9: 1.419
# BNTX.US_9: 1.328
# AKTS.US: 1.312
# FACE.ES: 1.299
# KPTI.US: 1.298
# MTH.US_9: 1.297
# AO.UK_9: 1.289
# MTN.US_9: 1.277
# HRMY.US: 1.258
# ST5.DE: 1.249
# RYN.US: 1.246
# SHW.US_9: 1.232
# SBGI.US_9: 1.232
# MKS.UK_9: 1.231
# KC.US_9: 1.227
# ATRY.ES: 1.216
# EXP.US_9: 1.210
# LONN.CH: 1.195
# CPR.IT_9: 1.193
# HO.FR_9: 1.188
# HEIA.NL_9: 1.173
# MAS.US_9: 1.170
# CRDA.UK_9: 1.165
# JMT.PT_9: 1.157
# T.US_9: 1.150
# OMC.US_9: 1.146
# MDRX.US_9: 1.120
# ORLY.US_9: 1.120
# SJM.US_9: 1.115
# BVI.FR_9: 1.105
# TXRH.US_9: 1.103

# 20.05.2025 Robust range scorer for the top 70 stocks:
#MBIO.US: 2.891
#NEXI.US: 2.200
#GTN.US_9: 1.513
#DOU.DE: 1.490
#KBH.US_9: 1.451
#GERN.US_9: 1.436
#CRNC.US_9: 1.428
#SITE.US_9: 1.364
#JBLU.US_9: 1.332
#BNTX.US_9: 1.328
#TPK.UK_9: 1.320
#IR.US_9: 1.320
#GN.DK_9: 1.309
#FACE.ES: 1.299
#MTH.US_9: 1.297
#HRMY.US: 1.258
#CAR.US_9: 1.244
#SBGI.US_9: 1.232
#MKS.UK_9: 1.231
#KC.US_9: 1.227
#PMT.US_9: 1.215
#EXP.US_9: 1.210
#CPR.IT_9: 1.193
#HO.FR_9: 1.188
#AM.FR: 1.188
#MIDD.US: 1.180
#MAS.US_9: 1.170
#WAL.US: 1.169
#PPG.US_9: 1.157
#JMT.PT_9: 1.157
#KEMIRA.FI_9: 1.154
#OMC.US_9: 1.146
#MONC.IT_9: 1.144
#RATOB.SE: 1.130
#BAKKA.NO_9: 1.128
#MDRX.US_9: 1.120
#ORLY.US_9: 1.120
#PVH.US_9: 1.118
#WRB.US_9: 1.106
#TBCG.UK_9: 1.105
#TXRH.US_9: 1.103
#TKA.DE_9: 1.100

# improved coherence
# 005420.KS: 1.453
# INFO - 1691.HK: 1.386
# INFO - TKMS.DE: 1.346
# INFO - 2158.HK: 1.331
# INFO - SIDO.JK: 1.328
# INFO - SUNTV.NS: 1.266
# INFO - RNA: 1.256
# INFO - RENT4.SA: 1.243
# INFO - MKS.L: 1.231
# INFO - 6632.T: 1.224
# INFO - EXP: 1.210
# INFO - 7575.T: 1.206
# INFO - 138040.KS: 1.193
# INFO - HO.PA: 1.188
# INFO - 2034.TW: 1.188
# INFO - MICC.AS: 1.184
# INFO - VOLTAS.NS: 1.181
# INFO - 2474.TW: 1.176
# INFO - MAS: 1.170
# INFO - BPT.AX: 1.156
# INFO - MONC.MI: 1.144
# INFO - HOMB: 1.131
# INFO - 600639.SS: 1.131
# INFO - 365550.KS: 1.130
# INFO - 7545.T: 1.119
# INFO - NHPC.NS: 1.113
# INFO - SIG.AX: 1.110
# INFO - ENOG.L: 1.108
# INFO - BVI.PA: 1.105
# INFO - 7414.T: 1.104
# INFO - 4369.T: 1.101
