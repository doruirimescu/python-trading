from Trading.symbols.constants import XTB_STOCK_TICKERS, XTB_STOCK_SYMBOLS_DICT, ALPHASPREAD_URL_DICT, ALPHASPREAD_URL_PATH
from Trading.symbols.alphaspread.search.url import get_alphaspread_symbol_url
import json

with open(ALPHASPREAD_URL_PATH, "r") as f:
    alphaspread_urls = json.load(f)

alphaspready_symbol_url = dict()
filtered_by_solvency = dict()
ALPHASPREAD_TICKERS_SET = set(ALPHASPREAD_URL_DICT.keys())
for symbol in XTB_STOCK_TICKERS:
    if symbol in ALPHASPREAD_TICKERS_SET:
        print(f"Skip - {symbol} already in alphaspread_urls")
        continue
    for sym in XTB_STOCK_SYMBOLS_DICT:
        if sym.startswith(symbol):
            xtb_sym = sym
            break
    try:
        print(f"Getting url for {symbol}")
        url = get_alphaspread_symbol_url(XTB_STOCK_SYMBOLS_DICT[xtb_sym]["description"])
        alphaspread_urls[symbol] = url[1]
        print(f'"{symbol}": "{url[1]}",')


    except Exception as e:
        print(f"Could not get url for {symbol}")
        alphaspread_urls[symbol] = None

    with open(ALPHASPREAD_URL_PATH, "w") as f:
            json.dump(alphaspread_urls, f, indent=4)
