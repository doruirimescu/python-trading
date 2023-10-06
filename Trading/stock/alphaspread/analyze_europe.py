import json
from typing import List, Optional
from alphaspread import analyze_url
from Trading.stock.constants import EUROPE_ANALYSIS_FILENAME
from Trading.symbols.constants import XTB_STOCK_SYMBOLS
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url

def get_europe_symbols(countries_list: Optional[List] = None ) -> List:
    with open(XTB_STOCK_SYMBOLS, "r") as f:
        symbols = json.load(f)
        # filter only symbols with eur currency
        symbols = [(symbol['symbol'],symbol['description'])
                   for key, symbol in symbols.items()
                   if symbol["currency"] == "EUR"
                   and symbol["groupName"] in countries_list]

    # Filter only symbols from the given countries
    return symbols


if __name__ == "__main__":
    europe_symbols = get_europe_symbols(["France", "Netherlands"])
    undervalued_symbols = []
    for sym, name in europe_symbols:
        try:
            # strip _9 from sym if it exists
            if sym.endswith("_9"):
                sym = sym[:-2]
            symbol, url = get_alphaspread_symbol_url(name)
            analysis = analyze_url(url, symbol)
            undervalued_symbols.append(analysis)
            import time
            time.sleep(1)
        except Exception as e:
            try:
                symbol, url = get_alphaspread_symbol_url(sym)
                analysis = analyze_url(url, symbol)
                undervalued_symbols.append(analysis)
            except Exception as e:
                print(e)
                print(f"Could not analyze {sym} - {name}")

    with open(EUROPE_ANALYSIS_FILENAME, "w") as f:
        json_str = json.dumps(
            [analysis.dict() for analysis in undervalued_symbols], indent=4
        )
        f.write(json_str)
