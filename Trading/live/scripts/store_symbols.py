from Trading.live.client.client import XTBTradingClient
from Trading.utils.write_to_file import write_to_json_file, read_json_file
from Trading.utils.data_processor import DataProcessor
from Trading.utils.data_processor import JsonFileRW
from Trading.config.config import USERNAME, PASSWORD, MODE, DATA_STORAGE_PATH
from Trading.utils.custom_logging import get_logger
from logging import Logger
from typing import Dict
import sys

ALL_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/all_symbols.json'
STC_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/stocks.json'
CMD_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/commodities.json'
FX_SYMBOLS_PATH  = DATA_STORAGE_PATH + 'symbols/forex.json'
CRT_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/crypto.json'
ETF_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/etf.json'
IND_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/index.json'

class AllSymbolsFromXTBStore(DataProcessor):
    def __init__(self, file_rw: JsonFileRW, logger: Logger):
        super().__init__(file_rw, logger)

    def _process_data(self, client: XTBTradingClient):
        all_xtb_symbols = client.get_all_symbols()
        self.iterate_items(all_xtb_symbols, client)

    def process_item(self, item, client: XTBTradingClient):
        info = client.get_symbol(item)
        symbol = info['symbol']
        self.data[symbol] = info

def store_symbols_from_client(client: XTBTradingClient, logger):
    file_rw = JsonFileRW(ALL_SYMBOLS_PATH, logger)
    asf = AllSymbolsFromXTBStore(file_rw, logger)
    asf.run(client=client)


def filter_from_file(category: str, path_to_write: str):
    all_symbols_dict = read_json_file(ALL_SYMBOLS_PATH)
    filtered = {k: v for k, v in all_symbols_dict.items() if v['categoryName'] == category}
    write_to_json_file(path_to_write, filtered)


def store_stocks():
    filter_from_file('STC', STC_SYMBOLS_PATH)


def store_commodities():
    filter_from_file('CMD', CMD_SYMBOLS_PATH)


def store_forex():
    filter_from_file('FX', FX_SYMBOLS_PATH)


def store_crypto():
    filter_from_file('CRT', CRT_SYMBOLS_PATH)


def store_etf():
    filter_from_file('ETF', ETF_SYMBOLS_PATH)


def store_indices():
    filter_from_file('IND', IND_SYMBOLS_PATH)

if __name__ == '__main__':
    MAIN_LOGGER = get_logger("store_symbols.py")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)
    all_xtb_symbols = client.get_all_symbols()
    store_symbols_from_client(client, MAIN_LOGGER)
