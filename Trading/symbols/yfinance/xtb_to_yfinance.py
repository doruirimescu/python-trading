from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor

from Trading.symbols.constants import (XTB_COMMODITY_SYMBOLS,
                                       XTB_STOCK_SYMBOLS_DICT,
                                       YAHOO_COMMODITY_SYMBOLS_PATH,
                                       YAHOO_STOCK_SYMBOLS_PATH)
from Trading.symbols.google_search_symbol import get_yfinance_symbol_url
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger("xtb_to_yfinance.py")

class YFinanceSymbolListProcessor(StatefulDataProcessor):
    def process_data(self, items):
        self._iterate_items(items)

    def process_item(self, item, iteration_index):
        yfinance_symbol = get_yfinance_symbol_url(item)
        self.data[item] = yfinance_symbol

class YFinanceDictListProcessor(StatefulDataProcessor):
    def process_item(self, item, iteration_index, items_dict):
        symbol = items_dict[item]['symbol']
        description = items_dict[item]['description']
        try:
            yfinance_symbol = get_yfinance_symbol_url(description)
            import time
            time.sleep(1)
        except Exception as e:
            LOGGER.error(f"Failed to get yfinance symbol for {description}")
            return
        self.data[symbol] = yfinance_symbol

def parse_commodities():
    yfsp = YFinanceSymbolListProcessor(JsonFileRW(YAHOO_COMMODITY_SYMBOLS_PATH, LOGGER), LOGGER)
    yfsp.run(symbols=XTB_COMMODITY_SYMBOLS)

def parse_stocks():
    yfsp = YFinanceDictListProcessor(JsonFileRW(YAHOO_STOCK_SYMBOLS_PATH, LOGGER), LOGGER)
    yfsp.run(items=XTB_STOCK_SYMBOLS_DICT.keys(), items_dict=XTB_STOCK_SYMBOLS_DICT)

parse_stocks()
