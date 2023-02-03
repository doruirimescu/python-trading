from Trading.live.client.client import XTBTradingClient
from Trading.utils.write_to_file import write_to_json_file, read_json_file
from Trading.config.config import USERNAME, PASSWORD, MODE, DATA_STORAGE_PATH
import logging
import sys

ALL_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/all_symbols.json'
STC_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/stocks.json'
CMD_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/commodities.json'
FX_SYMBOLS_PATH  = DATA_STORAGE_PATH + 'symbols/forex.json'
CRT_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/crypto.json'
ETF_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/etf.json'
IND_SYMBOLS_PATH = DATA_STORAGE_PATH + 'symbols/index.json'


def store_symbols_from_client():
    if "real" == MODE:
        print("Trading with a live client. Do you wish to continue ? y/n")
        should_continue = input().strip()
        if should_continue.lower() != "y":
            sys.exit(0)

    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    all_symbols = client.get_all_symbols()

    data_dict = dict()
    for s in all_symbols:
        info = client.get_symbol(s)
        symbol = info['symbol']
        data_dict[symbol] = info
        print(f"Processing symbol {s}")

    write_to_json_file(ALL_SYMBOLS_PATH, data_dict)


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
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True
