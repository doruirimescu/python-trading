from Trading.symbols.constants import ALPHASPREAD_URL_DICT, append_to_alphaspread_url_dict
from Trading.stock.alphaspread.search_alphaspread_symbol_url import search_alphaspread_symbol_url
from typing import Tuple

def get_alphaspread_url_from_ticker(ticker: str) -> Tuple[str, str]:
    if ticker in ALPHASPREAD_URL_DICT and ALPHASPREAD_URL_DICT[ticker]:
        if ticker.lower() not in ALPHASPREAD_URL_DICT[ticker].lower():
            print(f"+++ Careful with {ticker} and {ALPHASPREAD_URL_DICT[ticker]}")
        return (ticker, ALPHASPREAD_URL_DICT[ticker])
    else:
        raise Exception(f"Could not find alphaspread url for {ticker}")

def get_alphaspread_url(stock_name: str) -> Tuple[str, str]:
    try:
        return get_alphaspread_url_from_ticker(stock_name)
    except Exception as e:
        print(f"Could not find alphaspread url for {stock_name}")
        symbol, url = search_alphaspread_symbol_url("alphaspread " + stock_name + " sumamry")
        if symbol and url:
            append_to_alphaspread_url_dict({stock_name: url})
            return (symbol, url)
