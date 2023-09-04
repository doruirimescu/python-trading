import json
from typing import List, Optional
import requests
from alphaspread import analyze_url
from constants import NASDAQ_ANALYSIS_FILENAME
from Trading.config.config import STOCKS_PATH


def get_europe_symbols(countries_list: Optional[List] = None ) -> List:
    with open(STOCKS_PATH, "r") as f:
        symbols = json.load(f)
        # filter only symbols with eur currency
        symbols = [symbol for symbol in symbols if symbol["currency"] == "EUR"]

    # Filter only symbols from the given countries
    if countries_list:
        symbols = [symbol for symbol in symbols if symbol["country"] in countries_list]
    return symbols


if __name__ == "__main__":
    europe_symbols = get_europe_symbols(["France", "Netherlands"])
    undervalued_symbols = []
    for symbol in europe_symbols:
        url = f"https://www.alphaspread.com/security/nasdaq/{symbol}/summary"
        try:
            analysis = analyze_url(url, symbol)
            undervalued_symbols.append(analysis)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

    with open(NASDAQ_ANALYSIS_FILENAME, "w") as f:
        json_str = json.dumps(
            [analysis.dict() for analysis in undervalued_symbols], indent=4
        )
        f.write(json_str)
