import json

from Trading.symbols.constants import (
    XTB_ALL_SYMBOLS_PATH,
    XTB_ALL_SYMBOLS_DICT,
    XTB_FAILING_SYMBOLS,
    XTB_STOCK_SYMBOLS_DICT,
    XTB_STOCK_SYMBOLS_PATH,
    XTB_ETF_SYMBOLS_DICT,
    XTB_ETF_SYMBOLS_PATH

)

for symbol in XTB_FAILING_SYMBOLS:
    if symbol in XTB_ALL_SYMBOLS_DICT:
        XTB_ALL_SYMBOLS_DICT.pop(symbol)
    if symbol in XTB_STOCK_SYMBOLS_DICT:
        XTB_STOCK_SYMBOLS_DICT.pop(symbol)
    if symbol in XTB_ETF_SYMBOLS_DICT:
        XTB_ETF_SYMBOLS_DICT.pop(symbol)

stock_symbols = [s for s in XTB_STOCK_SYMBOLS_DICT]
for symbol in stock_symbols:
    if ('close only' in XTB_STOCK_SYMBOLS_DICT[symbol]['description'] or
        "CLOSE ONLY" in XTB_STOCK_SYMBOLS_DICT[symbol]['description'] or
        "Close only" in XTB_STOCK_SYMBOLS_DICT[symbol]['description']):
        XTB_STOCK_SYMBOLS_DICT.pop(symbol)
        print(symbol)

with open(XTB_ALL_SYMBOLS_PATH, 'w') as f:
    json.dump(XTB_ALL_SYMBOLS_DICT, f, indent=4)

with open(XTB_STOCK_SYMBOLS_PATH, 'w') as f:
    json.dump(XTB_STOCK_SYMBOLS_DICT, f, indent=4)

with open(XTB_ETF_SYMBOLS_PATH, 'w') as f:
    json.dump(XTB_ETF_SYMBOLS_DICT, f, indent=4)
