from Trading.utils.ratio.ratio import Ratio, DateNotFoundError, CurrentHolding
from stateful_data_processor.file_rw import JsonFileRW
import operator
from typing import List, Optional
from Trading.model.trade import (
        Trade,
        analyze_trades,
        StrategySummary,
        aggregate_analysis_results,
        TradesAnalysisResult,
    )

def backtest_ratio(ratio: Ratio, std_scaler, logger) -> Optional[TradesAnalysisResult]:
    trades = []
    if ratio.ratio_values != ratio.calculate_ratio():
        raise Exception("Error in calculating ratio")

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
            and abs(current_value - ratio.mean) >= std_scaler * ratio.std
        ):
            logger.info(f"Found a peak at date: {entry_date}")
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
            if current_holding == CurrentHolding.DENOMINATOR:
                next_date_at_mean, index = ratio.get_next_date_cross_mean(entry_date, operator.lt)
                exit_prices = ratio.get_denominator_prices_at_date(next_date_at_mean)
            elif current_holding == CurrentHolding.NUMERATOR:
                next_date_at_mean, index = ratio.get_next_date_cross_mean(entry_date, operator.gt)
                exit_prices = ratio.get_numerator_prices_at_date(next_date_at_mean)

            logger.info(f"Closing on: {next_date_at_mean}")
            for i, p in enumerate(exit_prices):
                trades[-1][i].exit_date = next_date_at_mean
                trades[-1][i].close_price = p
                trades[-1][i].calculate_max_drawdown_price_diff(
                    ratio.histories[trade_tuple[i].symbol]
                )
            current_holding = CurrentHolding.NONE
        except DateNotFoundError:
            logger.info(f"No date found at mean for {entry_date}")
            trades.pop()
            break

    tuple_analyses = []

    for trade_tuple in trades:
        # if the trade_tuple does not have a closing price, we should not analyze it
        trade_tuple = [t for t in trade_tuple if t.close_price]
        # logger.info(f"Trade tuple: {trade_tuple}")
        analysis = analyze_trades(
            trade_tuple, StrategySummary(False, 1000, 1, "USD", "STC")
        )
        if analysis is None:
            continue
        tuple_analyses.append(analysis)

    if not tuple_analyses:
        return None

    trade_analysis_result = aggregate_analysis_results(tuple_analyses)

    # print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    # trade_analysis_result.print()
    # print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    # print()

    return trade_analysis_result
