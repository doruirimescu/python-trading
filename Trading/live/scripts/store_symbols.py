from Trading.live.client.client import XTBTradingClient
from Trading.utils.data_processor import DataProcessor, JsonFileRW
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.symbols.constants import (
    XTB_ALL_SYMBOLS_PATH,
    XTB_STOCK_SYMBOLS_PATH,
    XTB_COMMODITY_SYMBOLS_PATH,
    XTB_FOREX_SYMBOLS_PATH,
    XTB_CRYPTO_SYMBOLS_PATH,
    XTB_ETF_SYMBOLS_PATH,
    XTB_INDEX_SYMBOLS_PATH,
)
from Trading.utils.custom_logging import get_logger
from logging import Logger

MAIN_LOGGER = get_logger("store_symbols.py")


class AllSymbolsFromXTBStore(DataProcessor):
    def __init__(self, file_rw: JsonFileRW, logger: Logger):
        super().__init__(file_rw, logger)

    def process_data(self, client: XTBTradingClient):
        all_xtb_symbols = client.get_all_symbols()
        self.iterate_items(all_xtb_symbols, client)

    def process_item(self, item, client: XTBTradingClient):
        info = client.get_symbol(item)
        symbol = info["symbol"]
        self.data[symbol] = info


def store_symbols_from_client(client: XTBTradingClient, logger):
    file_rw = JsonFileRW(XTB_ALL_SYMBOLS_PATH, logger)
    asf = AllSymbolsFromXTBStore(file_rw, logger)
    asf.run(client=client)


def filter_from_file(category: str, path_to_write: str):
    file_rw = JsonFileRW(path_to_write, MAIN_LOGGER)
    all_symbols_dict = file_rw.read()
    filtered = {
        k: v
        for k, v in all_symbols_dict.items()
        if v["categoryName"] == category
        and "close only" not in v["description"].lower()
    }

    file_rw.write(filtered)


def store_stocks():
    filter_from_file("STC", XTB_STOCK_SYMBOLS_PATH)

def store_commodities():
    filter_from_file("CMD", XTB_COMMODITY_SYMBOLS_PATH)


def store_forex():
    filter_from_file("FX", XTB_FOREX_SYMBOLS_PATH)


def store_crypto():
    filter_from_file("CRT", XTB_CRYPTO_SYMBOLS_PATH)


def store_etf():
    filter_from_file("ETF", XTB_ETF_SYMBOLS_PATH)


def store_indices():
    filter_from_file("IND", XTB_INDEX_SYMBOLS_PATH)


if __name__ == "__main__":
    # client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)
    # all_xtb_symbols = client.get_all_symbols()
    # store_symbols_from_client(client, MAIN_LOGGER)
    store_stocks()
    # store_commodities()
    # store_forex()
    # store_crypto()
    # store_etf()
    # store_indices()
