from Trading.live.client.client import XTBLoggingClient
from Trading.config.config import USERNAME, PASSWORD, MODE, RATIO_STOCKS_PATH
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.utils.visualize import plot_list_dates
from Trading.utils.ratio.combinatorics import get_ith_ratio
from Trading.model.datasource import DataSourceEnum
from Trading.live.caching.caching import get_last_n_candles_from_date
from typing import Optional, Dict
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, date
from dataclasses import dataclass
from typing import List
from Trading.utils.ratio.ratio import Ratio
from Trading.utils.calculations import calculate_mean
from Trading.live.ratio.backtest import backtest_ratio
from Trading.live.ratio.heap import Heap
from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

#! Used for in-memory caching
HISTORIES_DICT = {}

DATA_SOURCE = DataSourceEnum.XTB
GET_DATA_BEFORE_DATE = datetime(2025, 1, 1)
STD_SCALER = 1.5

N_CHOOSE_K = 5

top_10_ratios = Heap(10, lambda x: x[0])


@dataclass
class Criterion:
    maximum_average_ratio_deviation: float
    min_n_peaks: int
    min_average_swing_size: float
    min_swing_size: Optional[float]
    max_peak_offset: float
    max_days_between_swings: int


#! TODO: Make moving mean, get MAD from mean, and then check if it is below a certain threshold
CRITERION = Criterion(
    maximum_average_ratio_deviation=0.05,
    min_n_peaks=5,
    min_average_swing_size=0.05,
    min_swing_size=0.05,
    max_peak_offset=0.01,
    max_days_between_swings=365 * 2,
)


class RatioProcessor(StatefulDataProcessor):
    def __init__(
        self, json_file_rw, logger, should_reload_ordering=False, should_reprocess=False
    ):
        super().__init__(json_file_rw, logger, should_reprocess=should_reprocess)

    def process_item(self, item, iteration_index):
        global top_10_ratios
        if iteration_index % 10000 == 0:
            MAIN_LOGGER.info(f"Processed {iteration_index} / {len(self.data)}")
        n, d = item
        ratio = Ratio(list(n), list(d))

        construct_ratio(ratio)
        # MAIN_LOGGER.info(f"Calculating ratio: {ratio.numerator} / {ratio.denominator}")
        ratio.calculate_ratio()
        # MAIN_LOGGER.info(f"Calculated ratio: {ratio.ratio_values[0:10]}")
        ratio_values = ratio.ratio_values
        ratio_dates = ratio.dates

        average_ratio = sum(ratio_values) / len(ratio_values)

        if abs(average_ratio - 1.0) >= CRITERION.maximum_average_ratio_deviation:
            self.data[str(ratio)] = None
            return False

        dates = [str(x) for x in ratio_dates]
        peak_dict = calculate_mean_crossing_peaks(ratio_values, dates)
        if not peak_dict:
            # MAIN_LOGGER.info("No peaks found")
            self.data[str(ratio)] = None
            return False
        n_peaks = len(peak_dict["values"])

        if n_peaks <= CRITERION.min_n_peaks:
            # MAIN_LOGGER.info("Not enough peaks found")
            self.data[str(ratio)] = None
            return False

        if peak_dict["mean_swing_size"] <= CRITERION.min_average_swing_size:
            # MAIN_LOGGER.info("Average swing size too small")
            self.data[str(ratio)] = None
            return False

        peak_offset = abs(sum(peak_dict["values"]) - n_peaks * average_ratio)

        if peak_offset >= CRITERION.max_peak_offset:
            # MAIN_LOGGER.info("Peak offset too large")
            self.data[str(ratio)] = None
            return False

        # print(
        #     f"Found a ratio with at least one swing per year: {ratio.numerator} / {ratio.denominator}"
        # )

        trade_analysis_result = backtest_ratio(ratio, STD_SCALER, self.logger)
        iteration_info = f"k: {N_CHOOSE_K} index: {iteration_index}"

        if trade_analysis_result:
            ar = trade_analysis_result.annualized_return
            top_10_ratios.push((ar, iteration_info, trade_analysis_result))
            self.data[str(ratio)] = trade_analysis_result
        else:
            self.data[str(ratio)] = None

        # plot_list_dates(
        #     ratio_values,
        #     dates,
        #     f"Iteration number {iteration_info}",
        #     "Ratio Value",
        #     peak_dict,
        #     std_scaler=STD_SCALER,
        #     show_cursor=True,
        # )


def calculate_mean_crossing_peaks(ratios, days) -> Optional[Dict]:
    peaks = [ratios[0]]
    peak_days = [datetime.fromisoformat(days[0])]
    mean = calculate_mean(ratios)
    mean_swing_size = 0
    for i in range(1, len(ratios)):
        if peaks[-1] > mean and ratios[i] > mean:
            if ratios[i] > peaks[-1]:
                peaks[-1] = ratios[i]
                days_i = datetime.fromisoformat(days[i])
                if (days_i - peak_days[-1]).days > CRITERION.max_days_between_swings:
                    return None
                peak_days[-1] = days_i
        elif peaks[-1] < mean and ratios[i] < mean:
            if ratios[i] < peaks[-1]:
                peaks[-1] = ratios[i]
                days_i = datetime.fromisoformat(days[i])
                if (days_i - peak_days[-1]).days > CRITERION.max_days_between_swings:
                    return None
                peak_days[-1] = days_i
        elif ratios[i] == mean:
            continue
        else:
            swing = abs(ratios[i] - peaks[-1])
            if swing > CRITERION.min_swing_size:
                days_i = datetime.fromisoformat(days[i])
                peaks.append(ratios[i])
                peak_days.append(days_i)
                mean_swing_size += swing

    mean_swing_size /= len(peaks)
    peak_dict = {
        "values": peaks,
        "dates": peak_days,
        "mean_swing_size": mean_swing_size,
    }
    return peak_dict


def construct_ratio(ratio: Ratio):
    for symbol in ratio.numerator:
        ratio.add_history(symbol, HISTORIES_DICT[symbol])

    for symbol in ratio.denominator:
        ratio.add_history(symbol, HISTORIES_DICT[symbol])

    ratio.eliminate_nonintersecting_dates()


def process_ratio(ratio: Ratio, iteration_info: str = ""):
    construct_ratio(ratio)
    # MAIN_LOGGER.info(f"Calculating ratio: {ratio.numerator} / {ratio.denominator}")
    ratio.calculate_ratio()
    # MAIN_LOGGER.info(f"Calculated ratio: {ratio.ratio_values[0:10]}")
    ratio_values = ratio.ratio_values
    ratio_dates = ratio.dates

    average_ratio = sum(ratio_values) / len(ratio_values)

    if abs(average_ratio - 1.0) >= CRITERION.maximum_average_ratio_deviation:
        return False

    dates = [str(x) for x in ratio_dates]
    peak_dict = calculate_mean_crossing_peaks(ratio_values, dates)
    if not peak_dict:
        # MAIN_LOGGER.info("No peaks found")
        return False
    n_peaks = len(peak_dict["values"])

    if n_peaks <= CRITERION.min_n_peaks:
        # MAIN_LOGGER.info("Not enough peaks found")
        return False

    if peak_dict["mean_swing_size"] <= CRITERION.min_average_swing_size:
        # MAIN_LOGGER.info("Average swing size too small")
        return False

    peak_offset = abs(sum(peak_dict["values"]) - n_peaks * average_ratio)

    if peak_offset >= CRITERION.max_peak_offset:
        # MAIN_LOGGER.info("Peak offset too large")
        return False

    print(
        f"Found a ratio with at least one swing per year: {ratio.numerator} / {ratio.denominator}"
    )

    trade_analysis_result = backtest_ratio(ratio, STD_SCALER, MAIN_LOGGER)
    if trade_analysis_result:
        ar = trade_analysis_result.annualized_return
        top_10_ratios.push((ar, iteration_info, trade_analysis_result))

    plot_list_dates(
        ratio_values,
        dates,
        f"Iteration number {iteration_info}",
        "Ratio Value",
        peak_dict,
        std_scaler=STD_SCALER,
        show_cursor=True,
    )

    return True


def analyze_indices():
    ratio_permutations_indices = [
        1250026,
        1632784,
        722555,
        1233727,
        492143,
        191787,
        1205160,
        1864742,
        1156050,
        183115,
    ]
    for i, ratio in enumerate(ratio_permutations_indices):
        r = get_ith_ratio(ALL_SYMBOLS, 5, ratio)
        r = Ratio(list(r[0]), list(r[1]))
        construct_ratio(r)
        r.calculate_ratio()
        process_ratio(r)


if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger("Main logger")
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
    N_DAYS = 2000
    ALL_SYMBOLS = [
        "PLD.US_9",
        "CCI.US_9",
        "EQIX.US_9",
        "WELL.US",
        "SPG.US_9",
        "BXP.US_9",
        "ARE.US_9",
        "VTR.US_9",
        "AMT.US_9",
        "PSA.US_9",
        "O.US_9",
        "AVB.US_9",
        "DLR.US_9",
        "VNO.US_9",
        "EXR.US_9",
        "HST.US_9",
    ]

    # Populate the history dict
    MAIN_LOGGER.info("Populating the history dict")
    for symbol in ALL_SYMBOLS:
        hist = get_last_n_candles_from_date(
            GET_DATA_BEFORE_DATE,
            Instrument(symbol, Timeframe("1D")),
            DATA_SOURCE,
            N_DAYS,
        )
        HISTORIES_DICT[symbol] = hist
    MAIN_LOGGER.info("Populated the history dict")

    USE_MANUAL = False

    MAIN_LOGGER.info(f"Total number of symbols: {len(ALL_SYMBOLS)}")

    # analyze_indices()

    from Trading.utils.ratio.combinatorics import get_all_ratios

    all_ratios = get_all_ratios(ALL_SYMBOLS, 5)
    file_rw = JsonFileRW(RATIO_STOCKS_PATH.joinpath(f"{str(GET_DATA_BEFORE_DATE.date())}_ratios.json"))
    r = RatioProcessor(file_rw, None)
    r.run(all_ratios)
    print(top_10_ratios)


#! TODO: Use History class, history cache, StatefulDataProcessor

# Best indices:
# 1250026 1632784 722555 1233727 492143 191787 1205160 1864742 1156050 183115
