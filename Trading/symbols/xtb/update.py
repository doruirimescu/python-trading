import logging
import os
from dotenv import load_dotenv
from Trading.live.client.client import XTBTradingClient

if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger("Main logger")
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("USD_STOCKS")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, mode, False)

    symbols = client.get_all_symbol_data()

    # get all symbols path
    from Trading.symbols.constants import XTB_ALL_SYMBOLS_PATH
    #write to json file
    import json
    with open(XTB_ALL_SYMBOLS_PATH, 'w') as f:
        json.dump({s["symbol"]:s for s in symbols}, f, indent=4)

    # update stocks
    stocks_dict = {}
    for symbol in symbols:
        if symbol["categoryName"] == "STC" and "US_4" not in symbol["symbol"]:
            stocks_dict[symbol["symbol"]] = symbol
    from Trading.symbols.constants import XTB_STOCK_SYMBOLS_PATH
    with open(XTB_STOCK_SYMBOLS_PATH, 'w') as f:
        json.dump(stocks_dict, f, indent=4)
