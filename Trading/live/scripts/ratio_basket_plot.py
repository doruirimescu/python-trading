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
from typing import List
from Trading.utils.ratio.ratio import (RatioGenerator, Ratio,
                                       RatioPermutationIndices, DateNotFoundError,
                                       CurrentHolding)
from Trading.utils.history import History
from Trading.utils.calculations import calculate_mean
from Trading.utils.data_processor import JsonFileRW

def exit():
    sys.exit(0)

trades_file_writer = JsonFileRW("trades.json")

@dataclass
class Criterion:
    maximum_average_ratio_deviation: float
    min_n_peaks: int
    min_average_swing_size: float
    min_swing_size: Optional[float]
    max_peak_offset: float
    max_days_between_swings: int

CRITERION = Criterion(maximum_average_ratio_deviation=0.05,
                      min_n_peaks=5,
                      min_average_swing_size=0.05,
                      min_swing_size = 0.05,
                      max_peak_offset=0.01,
                      max_days_between_swings=365*2)

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
    peak_dict = {"values": peaks,
                 "dates": peak_days,
                 "mean_swing_size": mean_swing_size}
    return peak_dict

def construct_ratio(ratio: Ratio, N_DAYS: int):
    for symbol in ratio.numerator:
        try:
            history_days = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), N_DAYS)
            h = History(**history_days)
        except Exception as e:
            MAIN_LOGGER.exception("Error getting data for symbol %s", symbol)
        ratio.add_history(symbol, history_days)

    for symbol in ratio.denominator:
        try:
            history_days = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), N_DAYS)
        except Exception as e:
            MAIN_LOGGER.exception("Error getting data for symbol %s", symbol)
        ratio.add_history(symbol, history_days)

    ratio.eliminate_nonintersecting_dates()
    ratio.calculate_ratio()

def calculate_ratio(ratio: Ratio, N_DAYS: int, iteration_info: str=""):
    construct_ratio(ratio, N_DAYS)
    ratio_values = ratio.ratio_values
    ratio_dates = ratio.dates

    average_ratio = sum(ratio_values) / len(ratio_values)

    if abs(average_ratio-1.0) >= CRITERION.maximum_average_ratio_deviation:
        return False

    dates = [str(x) for x in ratio_dates]
    peak_dict = calculate_mean_crossing_peaks(ratio_values, dates)
    if not peak_dict:
        return False
    n_peaks = len(peak_dict["values"])

    if n_peaks <= CRITERION.min_n_peaks:
        return False

    if peak_dict["mean_swing_size"] <= CRITERION.min_average_swing_size:
        return False

    peak_offset=abs(sum(peak_dict["values"]) - n_peaks * average_ratio)

    if peak_offset >= CRITERION.max_peak_offset:
        return False

    print(f"Found a ratio with at least one swing per year: {ratio.numerator} / {ratio.denominator}")
    plot_list_dates(ratio_values, dates, f'Iteration number {iteration_info}', 'Ratio Value', peak_dict, show_cursor=True)

    trades = []
    if ratio_values != ratio.calculate_ratio():
        raise Exception("Error in calculating ratio")

    from Trading.algo.strategy.trade import Trade, analyze_trades, StrategySummary
    current_holding = CurrentHolding.NONE
    for peak, entry_date in zip(peak_dict["values"], peak_dict["dates"]):
        trade_tuple: List[Trade] = []
        if abs(peak - ratio.mean) > 1.5 * ratio.std:
            #! At high peak, buy the denominator
            entry_prices = ratio.get_denominator_prices_at_date(entry_date)
            for price, sym in zip(entry_prices, ratio.denominator):
                if not price:
                    raise Exception("Price is None")
                trade_tuple.append(Trade(cmd=0, entry_date=entry_date, open_price=price, symbol=sym))
            current_holding = CurrentHolding.DENOMINATOR
        elif abs(peak - ratio.mean) < 1.5*ratio.std:
            #! At low peak, buy the numerator
            prices = ratio.get_numerator_prices_at_date(entry_date)
            for price, sym in zip(prices, ratio.numerator):
                if not price:
                    raise Exception("Price is None")
                trade_tuple.append(Trade(cmd=0, entry_date=entry_date, open_price=price, symbol=sym))
            current_holding = CurrentHolding.NUMERATOR
        if trade_tuple:
            trades.append(trade_tuple)
        if current_holding == CurrentHolding.NONE:
            continue
        try:
            next_date_at_mean = ratio.get_next_date_at_mean(entry_date)
            if current_holding == CurrentHolding.DENOMINATOR:
                exit_prices = ratio.get_denominator_prices_at_date(str(next_date_at_mean))
            elif current_holding == CurrentHolding.NUMERATOR:
                exit_prices = ratio.get_numerator_prices_at_date(str(next_date_at_mean))
            for i, p in enumerate(exit_prices):
                trades[-1][i].exit_date = next_date_at_mean
                trades[-1][i].close_price = p
                trades[-1][i].calculate_max_drawdown_price_diff(ratio.histories[trade_tuple[i].symbol])
            current_holding = CurrentHolding.NONE
        except DateNotFoundError:
            trades.pop()
    trades = [trade for trade_tuple in trades for trade in trade_tuple]
    trades_file_writer.write(trades)
    analyze_trades(trades, StrategySummary(N_DAYS, False, 1000, 1, 'USD', 'STC'))
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
        RatioPermutationIndices(5, 0, 339),
        # RatioPermutationIndices(5, 0, 642),
        # RatioPermutationIndices(5, 0, 636),
        # RatioPermutationIndices(5, 0, 642),
        # RatioPermutationIndices(5, 0, 677),
        # RatioPermutationIndices(5, 0, 2533)
        ]
    ratios = RatioGenerator(ALL_SYMBOLS)
    ratio_permutations = ratios.get_permutations(ratio_permutations)

    for ratio in ratio_permutations:
        calculate_ratio(ratio, N_DAYS)

    # r = RatioGenerator(ALL_SYMBOLS, 5)
    # r._process = calculate_ratio
    # r.run(N_DAYS=N_DAYS)
