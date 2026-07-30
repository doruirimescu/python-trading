import argparse
import sys

from stateful_data_processor.file_rw import JsonFileRW

from Trading.stock.constants import (HELSINKI_NASDAQ_ANALYSIS_FILENAME,
                                     NASDAQ_ANALYSIS_FILENAME,
                                     SP500_ANALYSIS_FILENAME)
from Trading.stock.gurufocus.valuation import analyze_via_gurufocus
from Trading.symbols.wrapper import (get_nasdaq_helsinki_symbols,
                                     get_nasdaq_symbols,
                                     get_sp500_symbols)
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger("analyze_nasdaq")


def analyze_nasdaq():
    symbols = sorted(get_nasdaq_symbols())
    data = analyze_via_gurufocus(symbols)
    JsonFileRW(NASDAQ_ANALYSIS_FILENAME, LOGGER).write(data)


def analyze_helsinki_nasdaq():
    symbols = sorted(get_nasdaq_helsinki_symbols())
    data = analyze_via_gurufocus(symbols)
    JsonFileRW(HELSINKI_NASDAQ_ANALYSIS_FILENAME, LOGGER).write(data)


def analyze_sp500():
    sp500 = get_sp500_symbols()  # {symbol: exchange}
    symbols = sorted(sp500.keys())
    data = analyze_via_gurufocus(symbols)
    JsonFileRW(SP500_ANALYSIS_FILENAME, LOGGER).write(data)


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--helsinki", action="store_true")
    arg.add_argument("--nasdaq", action="store_true")
    arg.add_argument("--sp500", action="store_true")
    args = arg.parse_args()

    if args.helsinki:
        analyze_helsinki_nasdaq()
    elif args.nasdaq:
        analyze_nasdaq()
    elif args.sp500:
        analyze_sp500()
    else:
        print("Please specify --helsinki, --nasdaq, or --sp500")
        sys.exit(1)
