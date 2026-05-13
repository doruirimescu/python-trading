import requests
from typing import List
from bs4 import BeautifulSoup
from yfinance import EquityQuery
import yfinance as yf


def get_nasdaq_symbols() -> List:
    query = EquityQuery('and', [
        EquityQuery('is-in', ['exchange', 'NMS']),
        EquityQuery('gt', ['intradaymarketcap', 10_000_000_000]),
    ])
    result = yf.screen(query, size=100, sortField='intradaymarketcap', sortAsc=False)
    return [q['symbol'] for q in result.get('quotes', [])]


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


def get_alphaspread_nasdaq_url(ticker: str):
    return f"https://www.alphaspread.com/security/nasdaq/{ticker}/summary"
