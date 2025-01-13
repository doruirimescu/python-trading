from Trading.live.client.client import XTBLoggingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.utils.visualize import plot_list_dates
from Trading.utils.ratio.combinatorics import get_ith_ratio
from Trading.utils.ratio.ratio import RatioGenerator
from Trading.model.datasource import DataSourceEnum
from Trading.live.caching.caching import get_last_n_candles_from_date
from typing import Optional, Dict
from dotenv import load_dotenv
import operator
import os
import logging
import sys
from datetime import datetime, date
from dataclasses import dataclass
from typing import List
from Trading.utils.ratio.ratio import Ratio, DateNotFoundError, CurrentHolding
from Trading.utils.calculations import calculate_mean
from Trading.live.ratio.backtest import backtest_ratio
from Trading.live.ratio.heap import Heap

def exit():
    sys.exit(0)

#! Used for in-memory caching
HISTORIES_DICT = {}

DATA_SOURCE = DataSourceEnum.XTB
GET_DATA_BEFORE_DATE = datetime(2025, 1, 1)
STD_SCALER = 1.5

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


def construct_ratio(ratio: Ratio, N_DAYS: int):
    for symbol in ratio.numerator:
        ratio.add_history(symbol, HISTORIES_DICT[symbol])

    for symbol in ratio.denominator:
        ratio.add_history(symbol, HISTORIES_DICT[symbol])

    ratio.eliminate_nonintersecting_dates()


def process_ratio(ratio: Ratio, N_DAYS: int, iteration_info: str = ""):
    construct_ratio(ratio, N_DAYS)
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

    # plot_list_dates(
    #     ratio_values,
    #     dates,
    #     f"Iteration number {iteration_info}",
    #     "Ratio Value",
    #     peak_dict,
    #     std_scaler=STD_SCALER,
    #     show_cursor=True,
    # )

    return True


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

    if USE_MANUAL:
        NOMINATOR_SYMBOLS = ["PLD.US_9", "CCI.US_9", "EQIX.US_9", "WELL.US", "SPG.US_9"]
        DENOMINATOR_SYMBOLS = [
            "PLD.US_9",
            "CCI.US_9",
            "DLR.US_9",
            "EXR.US_9",
            "HST.US_9",
        ]
        calculate_ratio(NOMINATOR_SYMBOLS, DENOMINATOR_SYMBOLS, N_DAYS, f"{1}_{1}")
        exit()

    MAIN_LOGGER.info(f"Total number of symbols: {len(ALL_SYMBOLS)}")

    # ratio_permutations_indices = [338, 641, 635, 676, 2532]  # 338, 641, 635, 676, 2532

    # for i, ratio in enumerate(ratio_permutations_indices):
    #     r = get_ith_ratio(ALL_SYMBOLS, 5, ratio)

    #     calculate_ratio(
    #         Ratio(list(r[0]), list(r[1])), N_DAYS, ratio_permutations_indices[i]
    #     )

    r = RatioGenerator(ALL_SYMBOLS, 5)
    r._process = process_ratio
    r.run(N_DAYS=N_DAYS)

    print(top_10_ratios)


#! TODO: Use History class, history cache, StatefulDataProcessor
