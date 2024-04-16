# get current file path

import json
import os
from pathlib import Path

__CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

__ALL_SYMBOLS_JSON = Path("all_symbols.json")
__COMMODITIES_JSON = Path("commodities.json")
__ETF_JSON = Path("etf.json")
__FOREX_JSON = Path("forex.json")
__STOCKS_JSON = Path("stocks.json")
__INDEX_JSON = Path("index.json")
__CRYPTO_JSON = Path("crypto.json")


# XTB
__XTB_SYMBOLS_PATH = __CURRENT_FILE_PATH.joinpath("xtb/")
XTB_ALL_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __ALL_SYMBOLS_JSON
XTB_STOCK_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __STOCKS_JSON
XTB_FOREX_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __FOREX_JSON
XTB_ETF_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __ETF_JSON
XTB_INDEX_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __INDEX_JSON
XTB_COMMODITY_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __COMMODITIES_JSON
XTB_CRYPTO_SYMBOLS_PATH = __XTB_SYMBOLS_PATH / __CRYPTO_JSON

with open(XTB_ALL_SYMBOLS_PATH, "r") as f:
    XTB_ALL_SYMBOLS_DICT = json.load(f)
    XTB_ALL_SYMBOLS = [symbol for symbol in XTB_ALL_SYMBOLS_DICT]


with open(XTB_STOCK_SYMBOLS_PATH, "r") as f:
    XTB_STOCK_SYMBOLS_DICT = json.load(f)
    XTB_STOCK_SYMBOLS = [symbol for symbol in XTB_STOCK_SYMBOLS_DICT]
    # The universal stock tickers, without the xtb-specific suffix
    XTB_STOCK_TICKERS = [symbol.split(".")[0] for symbol in XTB_STOCK_SYMBOLS]

with open(XTB_ETF_SYMBOLS_PATH, "r") as f:
    XTB_ETF_SYMBOLS_DICT = json.load(f)
    XTB_ETF_SYMBOLS = [symbol for symbol in XTB_ETF_SYMBOLS_DICT]

with open(XTB_INDEX_SYMBOLS_PATH, "r") as f:
    XTB_INDEX_SYMBOLS_DICT = json.load(f)
    XTB_INDEX_SYMBOLS = [symbol for symbol in XTB_INDEX_SYMBOLS_DICT]

with open(XTB_COMMODITY_SYMBOLS_PATH, "r") as f:
    XTB_COMMODITY_SYMBOLS_DICT = json.load(f)
    XTB_COMMODITY_SYMBOLS = [symbol for symbol in XTB_COMMODITY_SYMBOLS_DICT]

with open(XTB_FOREX_SYMBOLS_PATH, "r") as f:
    XTB_FOREX_SYMBOLS_DICT = json.load(f)
    XTB_FOREX_SYMBOLS = [symbol for symbol in XTB_FOREX_SYMBOLS_DICT]

with open(XTB_CRYPTO_SYMBOLS_PATH, "r") as f:
    XTB_CRYPTO_SYMBOLS_DICT = json.load(f)
    XTB_CRYPTO_SYMBOLS = [symbol for symbol in XTB_CRYPTO_SYMBOLS_DICT]

# ALPHASPREAD
ALPHASPREAD_PATH = __CURRENT_FILE_PATH.joinpath("alphaspread/")
ALPHASPREAD_URL_PATH = ALPHASPREAD_PATH.joinpath("urls.json")

with open(ALPHASPREAD_URL_PATH, "r") as f:
    ALPHASPREAD_URL_DICT = json.load(f)

# YAHOO FINANCE
YAHOO_FINANCE_SYMBOLS_PATH = __CURRENT_FILE_PATH.joinpath("yfinance/")
YAHOO_COMMODITY_SYMBOLS_PATH = YAHOO_FINANCE_SYMBOLS_PATH / __COMMODITIES_JSON
YAHOO_STOCK_SYMBOLS_PATH = YAHOO_FINANCE_SYMBOLS_PATH / __STOCKS_JSON

with open(YAHOO_STOCK_SYMBOLS_PATH, "r") as f:
    YAHOO_STOCK_SYMBOLS_DICT = json.load(f)
    YAHOO_STOCK_SYMBOLS = [symbol for symbol in YAHOO_STOCK_SYMBOLS_DICT]
