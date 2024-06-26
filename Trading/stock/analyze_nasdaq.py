import argparse
import sys
from time import sleep

from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.constants import (HELSINKI_NASDAQ_ANALYSIS_FILENAME,
                                     NASDAQ_ANALYSIS_FILENAME)
from Trading.symbols.wrapper import (get_alphaspread_nasdaq_url,
                                     get_nasdaq_helsinki_symbols,
                                     get_nasdaq_symbols)
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger("analyze_nasdaq")
SLEEP_TIME = 2.0

class AlphaspreadNasdaqProcessor(StatefulDataProcessor):
    def process_item(self, item, iteration_index: int):
        symbol = item
        url = get_alphaspread_nasdaq_url(symbol)
        try:
            analysis = analyze_url(url, symbol)
        except Exception as e:
            LOGGER.error(f"Error processing {url}: {e}")
            analysis = None
        self.data[symbol] = analysis.dict()
        sleep(SLEEP_TIME)

def analyze_nasdaq():
    nasdaq_symbols = get_nasdaq_symbols()
    nasdaq_symbols = sorted(nasdaq_symbols)
    json_file_rw = JsonFileRW(NASDAQ_ANALYSIS_FILENAME, LOGGER)
    anp = AlphaspreadNasdaqProcessor(json_file_rw, LOGGER)
    anp.run(nasdaq_symbols)

def analyze_helsinki_nasdaq():
    nasdaq_symbols = get_nasdaq_helsinki_symbols()
    nasdaq_symbols = sorted(nasdaq_symbols)

    json_file_rw = JsonFileRW(HELSINKI_NASDAQ_ANALYSIS_FILENAME, LOGGER)
    anp = AlphaspreadNasdaqProcessor(json_file_rw, LOGGER)
    anp.run(nasdaq_symbols)

if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--helsinki", action="store_true")
    arg.add_argument("--nasdaq", action="store_true")
    args = arg.parse_args()

    if args.helsinki:
        analyze_helsinki_nasdaq()
    elif args.nasdaq:
        analyze_nasdaq()
    else:
        print("Please specify --helsinki or --nasdaq")
        sys.exit(1)
