import json
from time import sleep
from Trading.symbols.wrapper import get_nasdaq_symbols
from Trading.symbols.constants import ALPHASPREAD_URL_DICT, ALPHASPREAD_URL_PATH

ticker_to_url = dict()
if __name__ == "__main__":
    nasdaq_symbols = get_nasdaq_symbols()

    for symbol in nasdaq_symbols:
        ALPHASPREAD_URL_DICT[symbol] = f"https://www.alphaspread.com/security/nasdaq/{symbol}/summary"
        print(symbol)

    with open(ALPHASPREAD_URL_PATH, "w") as f:
        json_str = json.dumps(
            ALPHASPREAD_URL_DICT, indent=4
        )
        f.write(json_str)
