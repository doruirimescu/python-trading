from Trading.live.client.client import LoggingClient, TradingClient
from Trading.instrument.instrument import Instrument
from Trading.instrument.timeframes import TIMEFRAMES_TO_NAME
from Trading.utils.calculations import round_to_two_decimals
from datetime import datetime
from typing import Optional, Tuple, List


# We should create one main daily report, which aggregates all the alerts
def get_total_swap_of_open_forex_trades_report(client: TradingClient) -> Tuple[str, List]:
    open_trade_swaps = client.get_swaps_of_forex_open_trades()
    print(open_trade_swaps)
    report = ""
    for symbol, swap in open_trade_swaps:
        if swap < 0.0:
            date_now = str(datetime.now().date())
            report +f"Open trade swap gone negative, symbol: {symbol} swap: {str(swap)} date:{date_now}\n"

    total_profit, total_swap, text_message, data = client.get_total_forex_open_trades_profit_and_swap()
    report += text_message
    report += f"\nTotal profit: {str(total_profit)} Total swap: {str(round_to_two_decimals(total_swap))}\n"
    biggest_swaps = client.get_top_ten_biggest_swaps()
    report += f"\nBiggest 10 swaps:\n"
    for sym, sl, ss in biggest_swaps[0:10]:
        report += "Pair:\t{}\tSwap long:{:>10}\tSwap short:{:>10}\n".format(
                            sym, sl, ss)
    return report, data


def is_symbol_price_below_value(client: LoggingClient,
                                symbol: str,
                                value: float) -> Optional[str]:
    info = client.get_symbol(symbol)
    price = float(info['ask'])
    if price < value:
        return f"Price of {symbol} has gone below {value}"
    return None


def is_symbol_price_above_value(client: LoggingClient,
                                symbol: str,
                                value: float) -> Optional[str]:
    info = client.get_symbol(symbol)
    price = float(info['bid'])
    if price > value:
        return f"Price of {symbol} has gone above {value}"
    return None


def is_symbol_price_below_last_n_intervals_low(client: LoggingClient,
                                               instrument: Instrument,
                                               n: int) -> Optional[str]:
    info = client.get_symbol(instrument.symbol)
    price = float(info['ask'])
    history = client.get_last_n_candles_history(instrument, n)['low'][:-1]
    minimum = min(history)
    if price < minimum:
        return (
            f"{instrument.symbol} price {price} has gone "
            f"below the past {n} {TIMEFRAMES_TO_NAME[instrument.timeframe]} timeframe low {minimum}"
        )
    return None


def is_symbol_price_above_last_n_intervals_low(client: LoggingClient,
                                               instrument: Instrument,
                                               n: int) -> Optional[str]:
    info = client.get_symbol(instrument.symbol)
    price = float(info['bid'])
    history = client.get_last_n_candles_history(instrument, n)['high'][:-1]
    maximum = max(history)
    if price > maximum:
        return (
            f"{instrument.symbol} price {price} has gone "
            f"above the past {n} {TIMEFRAMES_TO_NAME[instrument.timeframe]} timeframe high {maximum}"
        )
    return None
