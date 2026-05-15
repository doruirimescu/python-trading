import argparse
import sys
from time import sleep
from typing import Callable

from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.constants import (HELSINKI_NASDAQ_ANALYSIS_FILENAME,
                                     NASDAQ_ANALYSIS_FILENAME,
                                     SP500_ANALYSIS_FILENAME)
from Trading.symbols.wrapper import (get_alphaspread_nasdaq_url,
                                     get_alphaspread_url,
                                     get_nasdaq_helsinki_symbols,
                                     get_nasdaq_symbols,
                                     get_sp500_symbols)
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger("analyze_nasdaq")
SLEEP_TIME = 2.0


class AlphaspreadProcessor(StatefulDataProcessor):
    def __init__(self, json_file_rw, logger, get_url: Callable[[str], str]):
        super().__init__(json_file_rw, logger)
        self._get_url = get_url

    def process_item(self, item, iteration_index: int):
        symbol = item
        url = self._get_url(symbol)
        try:
            analysis = analyze_url(url, symbol)
            self.data[symbol] = analysis.dict()
        except Exception as e:
            LOGGER.error(f"Error processing {url}: {e}")
        sleep(SLEEP_TIME)


def analyze_nasdaq():
    symbols = sorted(get_nasdaq_symbols())
    processor = AlphaspreadProcessor(
        JsonFileRW(NASDAQ_ANALYSIS_FILENAME, LOGGER), LOGGER,
        get_url=get_alphaspread_nasdaq_url,
    )
    processor.run(symbols)


def analyze_helsinki_nasdaq():
    symbols = sorted(get_nasdaq_helsinki_symbols())
    processor = AlphaspreadProcessor(
        JsonFileRW(HELSINKI_NASDAQ_ANALYSIS_FILENAME, LOGGER), LOGGER,
        get_url=get_alphaspread_nasdaq_url,
    )
    processor.run(symbols)


def analyze_sp500():
    sp500 = get_sp500_symbols()  # {symbol: alphaspread_exchange}
    symbols = sorted(sp500.keys())
    processor = AlphaspreadProcessor(
        JsonFileRW(SP500_ANALYSIS_FILENAME, LOGGER), LOGGER,
        get_url=lambda sym: get_alphaspread_url(sym, sp500[sym]),
    )
    processor.run(symbols)


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
