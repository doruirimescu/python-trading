from Trading.symbols.constants import ALPHASPREAD_URL_DICT
from Trading.symbols.google_search_symbol import get_alphaspread_symbol_url
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
        return get_alphaspread_symbol_url(stock_name)
