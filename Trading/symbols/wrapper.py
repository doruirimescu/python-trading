import requests
from typing import List, Set
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT, XTB_STOCK_SYMBOLS_DICT, XTB_STOCK_TICKERS
from bs4 import BeautifulSoup


def get_nasdaq_symbols() -> List:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    }
    res = requests.get(
        "https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers=headers
    )
    main_data = res.json()["data"]["data"]["rows"]
    symbols = []
    for i in range(len(main_data)):
        symbols.append(main_data[i]["symbol"])
    return symbols


def get_nasdaq_helsinki_symbols() -> List:
    headers = {
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        )
    }
    url = "https://www.nasdaqomxnordic.com/aktier/listed-companies/helsinki"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    tickers = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) > 1:
            tickers.append(cells[1].text)
    return tickers


def filter_xtb_symbols(countries: Set[str] = {}, currencies: Set[str] = {}) -> List:
    return [
        symbol
        for symbol in XTB_ALL_SYMBOLS_DICT
        if (not currencies or XTB_ALL_SYMBOLS_DICT[symbol]["currency"] in currencies)
        and (not countries or XTB_ALL_SYMBOLS_DICT[symbol]["groupName"] in countries)
    ]

def get_alphaspread_nasdaq_url(ticker: str):
    return f"https://www.alphaspread.com/security/nasdaq/{ticker}/summary"
