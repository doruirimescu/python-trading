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
import os
import logging
import sys
from datetime import datetime, date
from dataclasses import dataclass
from typing import List
from Trading.utils.ratio.ratio import Ratio, DateNotFoundError, CurrentHolding
from Trading.utils.calculations import calculate_mean
from stateful_data_processor.file_rw import JsonFileRW


def exit():
    sys.exit(0)


trades_file_writer = JsonFileRW(
    "/home/doru/personal/trading/Trading/live/ratio/trades.json"
)
analysis_file_writer = JsonFileRW(
    "/home/doru/personal/trading/Trading/live/ratio/analysis.json"
)

HISTORIES_DICT = {}
DATA_SOURCE = DataSourceEnum.XTB
GET_DATA_BEFORE_DATE = datetime(2025, 1, 1)


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
    STD_SCALER = 1.5
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
    # plot_list_dates(
    #     ratio_values,
    #     dates,
    #     f"Iteration number {iteration_info}",
    #     "Ratio Value",
    #     peak_dict,
    #     std_scaler=STD_SCALER,
    #     show_cursor=True,
    # )

    trades = []
    if ratio_values != ratio.calculate_ratio():
        raise Exception("Error in calculating ratio")

    from Trading.model.trade import (
        Trade,
        analyze_trades,
        StrategySummary,
        aggregate_analysis_results,
    )

    current_holding = CurrentHolding.NONE
    # for peak, entry_date in zip(peak_dict["values"], peak_dict["dates"]):
    index = 0
    while index < len(ratio.ratio_values):
        current_value = ratio.ratio_values[index]
        entry_date = ratio.dates[index]
        trade_tuple: List[Trade] = []
        #! WE SHOULD NOT LOOK AT ABS OF CURRENT VALUE - MEAN
        if (
            current_holding == CurrentHolding.NONE
            and abs(current_value - ratio.mean) >= STD_SCALER * ratio.std
        ):
            MAIN_LOGGER.info(f"Found a peak at date: {entry_date}")
            if current_value > ratio.mean:
                #! At high peak, buy the denominator
                entry_prices = ratio.get_denominator_prices_at_date(entry_date)
                current_holding = CurrentHolding.DENOMINATOR
                d_n = ratio.denominator
            else:
                #! At low peak, buy the numerator
                entry_prices = ratio.get_numerator_prices_at_date(entry_date)
                current_holding = CurrentHolding.NUMERATOR
                d_n = ratio.numerator
            for price, sym in zip(entry_prices, d_n):
                if not price:
                    raise Exception("Price is None")
                trade_tuple.append(
                    Trade(cmd=0, entry_date=entry_date, open_price=price, symbol=sym)
                )
            trades.append(trade_tuple)
        if current_holding == CurrentHolding.NONE:
            index += 1
            continue
        try:

            next_date_at_mean, index = ratio.get_next_date_at_mean(entry_date)
            MAIN_LOGGER.info(f"Closing on: {next_date_at_mean}")
            if current_holding == CurrentHolding.DENOMINATOR:
                exit_prices = ratio.get_denominator_prices_at_date(next_date_at_mean)
            elif current_holding == CurrentHolding.NUMERATOR:
                exit_prices = ratio.get_numerator_prices_at_date(next_date_at_mean)
            for i, p in enumerate(exit_prices):
                trades[-1][i].exit_date = next_date_at_mean
                trades[-1][i].close_price = p
                trades[-1][i].calculate_max_drawdown_price_diff(
                    ratio.histories[trade_tuple[i].symbol]
                )
            current_holding = CurrentHolding.NONE
        except DateNotFoundError:
            MAIN_LOGGER.info(f"No date found at mean for {entry_date}")
            trades.pop()
            break
    tuple_analyses = []
    for trade_tuple in trades:
        # if the trade_tuple does not have a closing price, we should not analyze it
        trade_tuple = [t for t in trade_tuple if t.close_price]
        MAIN_LOGGER.info(f"Trade tuple: {trade_tuple}")
        analysis = analyze_trades(
            trade_tuple, StrategySummary(False, 1000, 1, "USD", "STC")
        )
        if analysis is None:
            continue
        analysis.print()
        tuple_analyses.append(analysis)

    plot_list_dates(
        ratio_values,
        dates,
        f"Iteration number {iteration_info}",
        "Ratio Value",
        peak_dict,
        std_scaler=STD_SCALER,
        show_cursor=True,
    )
    if not tuple_analyses:
        return False
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    aggregate_analysis_results(tuple_analyses).print()
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

    trades = [trade for trade_tuple in trades for trade in trade_tuple]
    trades_dict = dict()
    trades_dict["trades"] = [t.dict() for t in trades]

    trades_file_writer.write(trades_dict)
    analysis = analyze_trades(trades, StrategySummary(False, 1000, 1, "USD", "STC"))
    analysis_file_writer.write(analysis.dict())
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


#! TODO: Use History class, history cache, StatefulDataProcessor
