from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import (get_date_now_cet,
                                get_datetime_now_cet,
                                get_seconds_to_next_date)
from Trading.utils.write_to_file import write_to_json_file, read_json_file

from Trading.config.config import USERNAME, PASSWORD, MODE
import logging
import sys


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

    write_to_json_file('data/symbols/all_symbols.json', data_dict)


def store_stocks():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'STC'}
    write_to_json_file('data/stocks.json', filtered)

def store_commodities():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'CMD'}
    write_to_json_file('data/symbols/commodities.json', filtered)

def store_forex():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'FX'}
    write_to_json_file('data/symbols/forex.json', filtered)

def store_crypto():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'CRT'}
    write_to_json_file('data/symbols/crypto.json', filtered)

def store_etf():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'ETF'}
    write_to_json_file('data/symbols/etf.json', filtered)

def store_indices():
    all_symbols_dict = read_json_file('data/symbols/all_symbols.json')
    filtered = {k:v for k,v in all_symbols_dict.items() if v['categoryName'] == 'IND'}
    write_to_json_file('data/symbols/index.json', filtered)

if __name__ == '__main__':
    start_time = get_datetime_now_cet()
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True
