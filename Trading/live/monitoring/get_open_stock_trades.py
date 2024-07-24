from datetime import date
from typing import Dict, List, Tuple

from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.processor import StatefulDataProcessor
from Trading.config.config import TMP_PATH
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT
from Trading.utils.custom_logging import get_logger

TMP_FILENAME = TMP_PATH / "monitor_stocks" / f"cv_price_{date.today()}.json"


def _preprocess_trades(trades) -> Dict[str, Tuple[str, float, float]]:
    items = dict()
    for trade in trades:
        if trade["closed"] or not trade["profit"]:
            continue

        symbol = trade["symbol"]
        s = XTB_ALL_SYMBOLS_DICT[symbol]
        cat = s["categoryName"]
        if cat not in ["STC"]:
            continue

        nominal_value = trade["nominalValue"]
        profit = trade["profit"]
        if(items.get(symbol, False)):
            items[symbol] = (
                nominal_value + items[symbol][0],
                profit + items[symbol][1],
            )
        else:
            items[symbol] = (
                nominal_value,
                profit,
            )
    return items


class OpenStockTradesProcessor(StatefulDataProcessor):
    def process_item(self, item, iteration_index, data):
        symbol = item
        nominal_value, profit = data[item]
        print(f"Processing item {item}")
        self.data[symbol] = [nominal_value, profit]


def get_data_from_broker(client, filename) -> Dict[str, List[float]]:
    """Gets stock contract value and profits from broker

    Args:
        client (_type_): _description_

    Returns:
        Dict[str, List[float, float]]: symbol : [contract value, profit]
    """
    LOGGER = get_logger("get_data_from_broker")
    json_file = JsonFileRW(filename)
    ostp = OpenStockTradesProcessor(json_file, logger=LOGGER)
    LOGGER.info("Retrieving data from broker")
    trades = client.get_open_trades()
    print(trades)
    items = _preprocess_trades(trades)
    ostp.run(items=items.keys(), data=items)
    return ostp.data


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from Trading.config.config import MODE, PASSWORD, USERNAME
    from Trading.live.client.client import XTBTradingClient
    from Trading.utils.custom_logging import get_logger

    LOGGER = get_logger("monitor_stocks")
    load_dotenv()
    username = os.getenv("USD_STOCKS")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, MODE, False)

    data = get_data_from_broker(client, TMP_FILENAME)
    print(data)
    LOGGER.info("Data retrieved from broker")
