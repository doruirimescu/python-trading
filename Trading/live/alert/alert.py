from enum import Enum
from Trading.live.client.client import LoggingClient
from datetime import datetime

class AlertCommand(Enum):
    GET_SWAP_OF_SYMBOL = 0
    GET_TOTAL_SWAP_OF_OPEN_TRADES_FOREX = 1
    GET_TOP_N_BIGGEST_SWAPS = 2
    IS_SYMBOL_PRICE_BELOW_VALUE = 3
    IS_SYMBOL_PRICE_ABOVE_VALUE = 4
    IS_SYMBOL_SWAP_BELOW_VALUE = 5
    IS_SYMBOL_PRICE_BELOW_LAST_N_INTERVALS_LOW = 6
    IS_SYMBOL_PRICE_ABOVE_LAST_N_INTERVALS_LOW = 7


# We should create one main daily report, which aggregates all the alerts

def get_total_swap_of_open_forex_trades_report(client: LoggingClient):
    open_trade_swaps = client.get_swaps_of_forex_open_trades()
    report = ""
    for symbol, swap in open_trade_swaps:
        if swap < 0.0:
            date_now = str(datetime.now().date())
            report +f"Open trade swap gone negative, symbol: {symbol} swap: {str(swap)} date:{date_now}\n"

    total_profit, total_swap, text_message = client.get_total_forex_open_trades_profit_and_swap()
    report += text_message
    report += f"\nTotal profit: {str(total_profit)} Total swap: {str(total_swap)}\n"
    biggest_swaps = client.get_top_ten_biggest_swaps()
    report += f"\nBiggest 10 swaps:\n"
    for sym, sl, ss in biggest_swaps[0:10]:
        report += "Pair:\t{}\tSwap long:{:>10}\tSwap short:{:>10}\n".format(
                            sym, sl, ss)
    return report
