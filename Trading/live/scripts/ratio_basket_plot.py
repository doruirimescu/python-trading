from Trading.live.client.client import XTBLoggingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument, Timeframe
from Trading.utils.visualize import plot_list_dates
from typing import Optional, Dict
from dotenv import load_dotenv
import os
import logging
import sys
from datetime import datetime
from dataclasses import dataclass
from Trading.utils.ratio.ratio import RatioGenerator, Ratio, RatioPermutationIndices

from Trading.utils.calculations import calculate_mean, calculate_standard_deviation
def exit():
    sys.exit(0)

def normalize_prices(history_days):
    p = history_days['close']
    p = [x/p[0] for x in p]
    return p

@dataclass
class Criterion:
    maximum_average_ratio_deviation: float
    min_n_peaks: int
    min_average_swing_size: float
    min_swing_size: Optional[float]
    max_peak_offset: float
    max_days_between_swings: int
    is_enabled: bool = False

CRITERION = Criterion(maximum_average_ratio_deviation=0.05,
                      min_n_peaks=5,
                      min_average_swing_size=0.05,
                      min_swing_size = 0.05,
                      max_peak_offset=0.01,
                      max_days_between_swings=365*2,
                      is_enabled=True)

def calculate_mean_crossing_peaks(ratios, days) -> Optional[Dict]:
    peaks = [ratios[0]]
    peak_days = [days[0]]
    mean = calculate_mean(ratios)
    mean_swing_size = 0

    for i in range(1, len(ratios)):
        if peaks[-1] > mean and ratios[i] > mean:
            if ratios[i] > peaks[-1]:
                peaks[-1] = ratios[i]
                peak_days[-1] = datetime.fromisoformat(days[i])
        elif peaks[-1] < mean and ratios[i] < mean:
            if ratios[i] < peaks[-1]:
                peaks[-1] = ratios[i]
                peak_days[-1] = datetime.fromisoformat(days[i])
        elif ratios[i] == mean:
            continue
        else:
            swing = abs(ratios[i] - peaks[-1])
            if swing > CRITERION.min_swing_size:
                days_i = datetime.fromisoformat(days[i])
                if (days_i - peak_days[-1]).days > CRITERION.max_days_between_swings:
                    return None
                peaks.append(ratios[i])
                peak_days.append(days_i)
                mean_swing_size += swing

    mean_swing_size /= len(peaks)

    peak_dict = {"values": peaks,
                 "dates": peak_days,
                 "mean_swing_size": mean_swing_size}
    return peak_dict

def calculate_ratio(ratio: Ratio, N_DAYS: int, iteration_info: str=""):
    numerator_total = [0] * N_DAYS
    denominator_total= [0] * N_DAYS

    for symbol in ratio.numerator:
        try:
            history_days = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), N_DAYS)
        except Exception as e:
            MAIN_LOGGER.exception("Error getting data for symbol %s", symbol)
        normalized_prices = normalize_prices(history_days)
        numerator_total = [x + y for x, y in zip(numerator_total, normalized_prices)]

    for symbol in ratio.denominator:
        try:
            history_days = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), N_DAYS)
        except Exception as e:
            MAIN_LOGGER.exception("Error getting data for symbol %s", symbol)
        normalized_prices = normalize_prices(history_days)
        denominator_total = [x + y for x, y in zip(denominator_total, normalized_prices)]

    ratio_values = []
    for i in range(N_DAYS):
        ratio_values.append(numerator_total[i] / denominator_total[i])

    average_ratio = sum(ratio_values) / len(ratio_values)

    if CRITERION.is_enabled and abs(average_ratio-1.0) >= CRITERION.maximum_average_ratio_deviation:
        return False

    dates = [str(x) for x in history_days['date']]

    peak_dict = calculate_mean_crossing_peaks(ratio_values, dates)
    if peak_dict is None:
        return False
    n_peaks = len(peak_dict["values"])

    if n_peaks <= CRITERION.min_n_peaks:
        return False

    if peak_dict["mean_swing_size"] <= CRITERION.min_average_swing_size:
        return False

    peak_offset=abs(sum(peak_dict["values"]) - n_peaks * average_ratio)

    if peak_offset >= CRITERION.max_peak_offset:
        return False

    swing_dates = peak_dict["dates"]

    for i in range(1, n_peaks):
        if (swing_dates[i] - swing_dates[i-1]).days > CRITERION.max_days_between_swings:
            return False

    print(f"Found a ratio with at least one swing per year: {ratio.numerator} / {ratio.denominator}")
    plot_list_dates(ratio_values, dates, f'Iteration number {iteration_info}', 'Ratio Value', peak_dict, show_cursor=True)
    return True

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
    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
    N_DAYS = 2000
    ALL_SYMBOLS = ['PLD.US_9','CCI.US_9', 'EQIX.US_9', 'WELL.US', 'SPG.US_9', 'BXP.US_9', 'ARE.US_9', 'VTR.US_9',
                   'AMT.US_9','PSA.US_9', 'O.US_9', 'AVB.US_9', 'DLR.US_9', 'VNO.US_9', 'EXR.US_9', 'HST.US_9']

    USE_MANUAL = False

    if USE_MANUAL:
        NOMINATOR_SYMBOLS = ['PLD.US_9', 'CCI.US_9', 'EQIX.US_9', 'WELL.US', 'SPG.US_9']
        DENOMINATOR_SYMBOLS = ['PLD.US_9', 'CCI.US_9', 'DLR.US_9', 'EXR.US_9', 'HST.US_9']
        calculate_ratio(NOMINATOR_SYMBOLS, DENOMINATOR_SYMBOLS, N_DAYS, f"{1}_{1}")
        exit()

    MAIN_LOGGER.info(f"Total number of symbols: {len(ALL_SYMBOLS)}")

    ratio_permutations = [
        RatioPermutationIndices(8, 4, 10718),
        RatioPermutationIndices(8, 4, 10543),
        RatioPermutationIndices(5, 0, 2533)]
    ratios = RatioGenerator(ALL_SYMBOLS, 8)
    ratio_permutations = ratios.get_permutations(ratio_permutations)
    for ratios in ratio_permutations:
        print(ratios)
        # calculate_ratio(ratios, N_DAYS)

    r = RatioGenerator(ALL_SYMBOLS, 5)
    r._process = calculate_ratio
    r.run(N_DAYS=N_DAYS)
