from Trading.alphaspread.google import get_first_google_result
from typing import Tuple


def get_alphaspread_symbol_url(stock_name: str) -> Tuple[str, str]:
    url = get_first_google_result("alphaspread " + stock_name)
    # Strip the symbol as the second last part of the url
    symbol = url.split("/")[-2]

    # Replace the last part of the url with "summary"
    splits = url.split("/")
    url = url.replace(splits[-1], "summary")

    return(symbol, url)
