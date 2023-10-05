# get current file path

import os
import json
from pathlib import Path
from Trading.symbols.xtb.failing_symbols import XTB_FAILING_SYMBOLS

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

# XTB
XTB_SYMBOLS_PATH = CURRENT_FILE_PATH.joinpath("xtb/")
XTB_ALL_SYMBOLS_PATH = XTB_SYMBOLS_PATH.joinpath("all_symbols.json")
XTB_STOCK_SYMBOLS_PATH = XTB_SYMBOLS_PATH.joinpath("stocks.json")
XTB_ETF_SYMBOLS_PATH = XTB_SYMBOLS_PATH.joinpath("etf.json")
with open(XTB_ALL_SYMBOLS_PATH, "r") as f:
    XTB_ALL_SYMBOLS_DICT = json.load(f)
    XTB_ALL_SYMBOLS = [symbol for symbol in XTB_ALL_SYMBOLS_DICT]


with open(XTB_STOCK_SYMBOLS_PATH, "r") as f:
    XTB_STOCK_SYMBOLS_DICT = json.load(f)
    XTB_STOCK_SYMBOLS = [symbol for symbol in XTB_STOCK_SYMBOLS_DICT]
    XTB_STOCK_TICKERS = [symbol.split(".")[0] for symbol in XTB_STOCK_SYMBOLS]

with open(XTB_ETF_SYMBOLS_PATH, "r") as f:
    XTB_ETF_SYMBOLS_DICT = json.load(f)
    XTB_ETF_SYMBOLS = [symbol for symbol in XTB_ETF_SYMBOLS_DICT]

# ALPHASPREAD
ALPHASPREAD_PATH = CURRENT_FILE_PATH.joinpath("alphaspread/")
ALPHASPREAD_URL_PATH = ALPHASPREAD_PATH.joinpath("urls.json")
