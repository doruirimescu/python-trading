import requests
from typing import Dict, List
from bs4 import BeautifulSoup
from yfinance import EquityQuery
import yfinance as yf

_YF_TO_ALPHASPREAD = {'NMS': 'nasdaq', 'NYQ': 'nyse', 'NGM': 'nasdaq', 'NCM': 'nasdaq'}


def get_nasdaq_symbols() -> List[str]:
    query = EquityQuery('and', [
        EquityQuery('is-in', ['exchange', 'NMS']),
        EquityQuery('gt', ['intradaymarketcap', 10_000_000_000]),
    ])
    result = yf.screen(query, size=100, sortField='intradaymarketcap', sortAsc=False)
    return [q['symbol'] for q in result.get('quotes', [])]


def _fetch_sp500_wikipedia() -> Dict[str, str]:
    """Returns {ticker: company_name} from Wikipedia's official S&P 500 constituents table."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find('table', {'id': 'constituents'})
    result = {}
    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) >= 2:
            ticker = cols[0].text.strip().replace('.', '-')
            name = cols[1].text.strip()
            result[ticker] = name
    return result


def get_sp500_symbols() -> Dict[str, str]:
    """Returns {ticker: alphaspread_exchange} for actual S&P 500 members per Wikipedia."""
    sp500_names = _fetch_sp500_wikipedia()
    sp500_tickers = set(sp500_names.keys())

    query = EquityQuery('and', [
        EquityQuery('is-in', ['exchange', 'NMS', 'NYQ', 'NGM', 'NCM']),
        EquityQuery('gt', ['intradaymarketcap', 1_000_000_000]),
    ])
    symbols: Dict[str, str] = {}
    for offset in (0, 250, 500):
        result = yf.screen(query, offset=offset, size=250,
                           sortField='intradaymarketcap', sortAsc=False)
        for q in result.get('quotes', []):
            ticker = q['symbol']
            if ticker in sp500_tickers:
                exchange = _YF_TO_ALPHASPREAD.get(q.get('exchange', ''), 'nyse')
                symbols[ticker] = exchange

    # Fall back to individual lookup for any S&P 500 tickers not found via screening
    for ticker in sp500_tickers - set(symbols.keys()):
        try:
            exch = yf.Ticker(ticker).fast_info.exchange
            symbols[ticker] = _YF_TO_ALPHASPREAD.get(exch, 'nyse')
        except Exception:
            symbols[ticker] = 'nyse'

    return symbols


def get_sp500_company_names() -> Dict[str, str]:
    """Returns {ticker: company_name} for S&P 500 from Wikipedia."""
    return _fetch_sp500_wikipedia()


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


def get_alphaspread_nasdaq_url(ticker: str) -> str:
    return f"https://www.alphaspread.com/security/nasdaq/{ticker}/summary"


def get_alphaspread_url(ticker: str, exchange: str) -> str:
    return f"https://www.alphaspread.com/security/{exchange}/{ticker}/summary"
