from exception_with_retry import exception_with_retry
import plotly.express as px

from Trading.live.client.client import XTBTradingClient
from Trading.config.config import ALL_SYMBOLS
from Trading.config.config import USERNAME, PASSWORD, MODE
from dotenv import load_dotenv

import os
import logging

# open all symbols file

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
            if trade['closed'] or not trade['profit']:
                continue

            symbol = trade['symbol']
            nominal_value = trade['nominalValue']
            print(f"Analysing symbol {symbol}")

            # Filter out other instruments
            s = ALL_SYMBOLS[symbol]
            cat = s['categoryName']
            if cat not in ['STC', 'ETF']:
                continue

            # Add up contract value and profit
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

        stock_contract_value_percentage = dict()
        stock_profits_percentage = dict()
        for symbol in stock_contract_value.keys():
            stock_contract_value_percentage[symbol] = stock_contract_value[symbol] / total_portfolio_contract_value
            stock_profits_percentage[symbol] = stock_profits[symbol] / total_portfolio_profit

        # Data for pie chart
        labels = list(stock_contract_value_percentage.keys())
        labels = [ALL_SYMBOLS[l]['description'] for l in labels]
        sizes = list(stock_contract_value_percentage.values())

        # Create the pie chart
        fig = px.pie(values=sizes, names=labels, title="Stock Contract Value Percentage")

        # Show the pie chart
        fig.show()

        print(stock_contract_value)
        print(stock_profits)


    monitor_once()
