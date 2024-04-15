from Trading.symbols.google_search_symbol import get_yfinance_symbol_url
from Trading.utils.write_to_file import write_to_json_file, extend_json_file, read_json_file
from Trading.utils.custom_logging import get_logger
LOGGER = get_logger(__file__)

def parse_commodities():
    from Trading.symbols.constants import XTB_COMMODITY_SYMBOLS, YAHOO_COMMODITY_SYMBOLS_PATH
    commodities = dict()
    for symbol in XTB_COMMODITY_SYMBOLS:
        # It's easiest to get the yfinance symbol by searching for the xtb symbol
        yfinance_symbol = get_yfinance_symbol_url(symbol)
        commodities[symbol] = yfinance_symbol

    write_to_json_file(YAHOO_COMMODITY_SYMBOLS_PATH, commodities)

def parse_stocks():
    from Trading.symbols.constants import XTB_STOCK_SYMBOLS_DICT, YAHOO_STOCK_SYMBOLS_PATH

    stocks = read_json_file(YAHOO_STOCK_SYMBOLS_PATH)
    try:
        for symbol in ["SHOP.US_9"]:
            if symbol in stocks:
                continue
            # It's easiest to get the yfinance symbol by searching for the xtb description
            description = XTB_STOCK_SYMBOLS_DICT[symbol]["description"]
            try:
                yfinance_symbol = get_yfinance_symbol_url(description)
                stocks[symbol] = yfinance_symbol
            except Exception as e:
                LOGGER.error(f"Could not process symbol for {symbol} {e}")
                continue
        write_to_json_file(YAHOO_STOCK_SYMBOLS_PATH, stocks)

    except KeyboardInterrupt as e:
        LOGGER.info(f"Last symbol: {symbol}")
        write_to_json_file(YAHOO_STOCK_SYMBOLS_PATH, stocks)

parse_stocks()
