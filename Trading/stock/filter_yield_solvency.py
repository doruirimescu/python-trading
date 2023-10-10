from Trading.symbols.constants import XTB_STOCK_TICKERS, XTB_STOCK_SYMBOLS_DICT, ALPHASPREAD_URL_DICT
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url
from Trading.stock.alphaspread.alphaspread import analyze_url

with open("dividend_yield.json", "r") as f:
    import json
    yields_per_symbol = json.load(f)

YIELD_FILTER = 7.0
SOLVENCY_FILTER = 55

# Filter
symbols = [symbol for symbol in yields_per_symbol]
for symbol in symbols:
    if yields_per_symbol[symbol] < 7.0:
        yields_per_symbol.pop(symbol)

alphaspready_symbol_url = dict()
filtered_by_solvency = dict()
for symbol in yields_per_symbol:
    if symbol not in ALPHASPREAD_URL_DICT:
        continue
    try:
        a = analyze_url(ALPHASPREAD_URL_DICT[symbol], symbol)
        if a.solvency_score < SOLVENCY_FILTER:
            continue
        filtered_by_solvency[symbol] = a
        print(f"Symbol: {symbol}, yield: {yields_per_symbol[symbol]}, alphaspread: {a}")
    except Exception as e:
        pass
    # if symbol in ALPHASPREAD_URL_DICT:
    #     continue
    # for sym in XTB_STOCK_SYMBOLS_DICT:
    #     if sym.startswith(symbol):
    #         xtb_sym = sym
    #         break
    # try:
    #     url = get_alphaspread_symbol_url(XTB_STOCK_SYMBOLS_DICT[xtb_sym]["description"])
    #     print(f'"{symbol}": "{url[1]}",')
    # except Exception as e:
    #     print(f"Could not get url for {symbol}")
    #     continue
print(f"Curated dividend yields: {yields_per_symbol}")
