from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.database.wrapper import update_open_trades, clear_open_trades
from dotenv import load_dotenv
import time

import os
import logging


def _update_open_trades(client):
    trades = client.get_open_trades()
    clear_open_trades()
    for trade in trades:
        if trade['closed'] == True or not trade['profit']:
                continue
        if trade['cmd'] != 0 and trade['cmd'] != 1:
            continue

        symbol = trade['symbol']
        instrument_type = None
        gross_profit = trade['profit']
        swap = trade['storage']
        cmd = trade['cmd']
        open_price = trade['open_price']
        timestamp_open = str(trade['open_time'])
        position_id = trade['position']
        order_id = trade['order']

        s = client.get_symbol(symbol)
        instrument_type = s['categoryName']

        update_open_trades(
            symbol, instrument_type, gross_profit, swap,
            cmd, open_price, timestamp_open, position_id, order_id)


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    while True:
        _update_open_trades(client)
        time.sleep(1)
