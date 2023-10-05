import json
from typing import List
import time
from Trading.symbols.constants import XTB_STOCK_SYMBOLS_DICT, ALPHASPREAD_URL_PATH
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url

def xtb_symbols() -> List:
    # Filter only symbols from the given countries
    return [(XTB_STOCK_SYMBOLS_DICT[symbol]['symbol'].split(".")[0],
             XTB_STOCK_SYMBOLS_DICT[symbol]['description']) for symbol in XTB_STOCK_SYMBOLS_DICT]

with open(ALPHASPREAD_URL_PATH, "r") as f:
    # load json
    json_str = f.read()
    data = json.loads(json_str)

if __name__ == "__main__":
    s = xtb_symbols()
    for sym, name in s:
        try:
            # strip _9 from sym if it exists
            if sym.endswith("_9"):
                sym = sym[:-2]
            symbol, url = get_alphaspread_symbol_url(name)
            data[symbol] = url
            time.sleep(1)
            print(f"Analyzed {sym} - {name}")

        except Exception as e:
            try:
                symbol, url = get_alphaspread_symbol_url(sym)
                data[symbol] = url
            except Exception as e:
                print(e)
                print(f"Could not analyze {sym} - {name}")
        break

with open(ALPHASPREAD_URL_PATH, "w") as f:
    json_str = json.dumps(
        data, indent=4
    )
    f.write(json_str)
