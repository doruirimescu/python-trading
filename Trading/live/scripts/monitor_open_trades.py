from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.database.add_contract_value_into_database import add_contract_value, delete_contract_value
from Trading.database.add_hedged_trade_profit_into_database import add_hedged_profit
from Trading.database.add_margin_level_into_database import add_margin_level
from dotenv import load_dotenv

import os
import logging

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

    contract_values = dict()
    margin_level = 0


    @exception_with_retry(n_retry=10, sleep_time_s=5.0)
    def monitor_once():
        hedged_profit = 0

        trades = client.get_open_trades()
        for trade in trades:
            if trade['closed'] == True or not trade['profit']:
                continue
            print(trade)
            symbol = trade['symbol']
            volume = trade['volume']

            if symbol == "AUDUSD" or symbol == "NZDUSD":
                hedged_profit += float(trade['profit'])

            s = client.get_symbol(symbol)
            cat = s['categoryName']

            leverage = 100/float(s['leverage'])
            if 'STC' in cat:
                continue
            contract_value = client.get_margin_trade(symbol, volume) * leverage
            if not contract_values.get(symbol):
                contract_values[symbol] = 0.0
            contract_values[symbol] += contract_value
        delete_contract_value()
        for k, v in contract_values.items():
            print(k, v)
            add_contract_value(k, v)

        add_hedged_profit('AUDUSD_NZDUSD', hedged_profit)

        margin_level = client.get_margin_level()
        add_margin_level(margin_level['balance'], margin_level['margin'],
                     margin_level['equity'], margin_level['margin_free'],
                     margin_level['margin_level'], margin_level['stockValue'])

    monitor_once()
