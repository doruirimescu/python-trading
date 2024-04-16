from Trading.utils.google_search import get_first_google_result, GoogleSearchFailed, GoogleSearcher
from Trading.utils.custom_logging import get_logger
from typing import Tuple

LOGGER = get_logger(__file__)

class AlphaSpreadSymbolNotFound(Exception):
    def __init__(self, symbol: str):
        message = f"Could not find alphaspread symbol for {symbol}"
        LOGGER.error(message)
        super().__init__(message)

def get_alphaspread_symbol_url(stock_name: str) -> Tuple[str, str]:
    try:
        url = get_first_google_result("alpha spread " + stock_name)
    except GoogleSearchFailed:
        raise AlphaSpreadSymbolNotFound(stock_name)
    if "alphaspread" not in url:
        raise AlphaSpreadSymbolNotFound(stock_name)
    # Strip the symbol as the second last part of the url
    symbol = url.split("/")[-2]

    # Replace the last part of the url with "summary"
    splits = url.split("/")
    url = url.replace(splits[-1], "summary")

    return(symbol, url)

class YahooFinanceSymbolNotFound(Exception):
    def __init__(self, symbol: str):
        message = f"Could not find yahoo finance symbol for {symbol}"
        LOGGER.error(message)
        super().__init__(message)

def get_yfinance_symbol_url(symbol: str) -> Tuple[str, str]:
    try:
        gs = GoogleSearcher(0.1)
        url = gs.get_first_google_result("yahoo finance " + symbol)
    except GoogleSearchFailed:
        raise YahooFinanceSymbolNotFound(symbol)
    if "finance.yahoo.com/quote" not in url:
        raise YahooFinanceSymbolNotFound(symbol)
    symbol = url.split("/")[-2]
    return(symbol, url)
