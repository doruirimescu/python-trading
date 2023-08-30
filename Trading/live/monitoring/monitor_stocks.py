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

# Monitor stock allocations

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

        stock_contract_value = dict()
        stock_profits = dict()

        trades = client.get_open_trades()
        for trade in trades:
            if trade['closed'] == True or not trade['profit']:
                continue

            symbol = trade['symbol']
            nominal_value = trade['nominalValue']

            s = client.get_symbol(symbol)
            cat = s['categoryName']
            if cat not in ['STC', 'ETF']:
                continue

            if not stock_contract_value.get(symbol):
                stock_contract_value[symbol] = nominal_value
                stock_profits[symbol] = trade['profit']
            else:
                stock_contract_value[symbol] += nominal_value
                stock_profits[symbol] += trade['profit']

            s = client.get_symbol(symbol)
            cat = s['categoryName']

        total_portfolio_contract_value = sum(stock_contract_value.values())
        total_portfolio_profit = sum(stock_profits.values())

        print(stock_contract_value)
        print(stock_profits)


    monitor_once()
