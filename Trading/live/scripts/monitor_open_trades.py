from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.database.add_contract_value_into_database import add_contract_value

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
    @exception_with_retry(n_retry=10, sleep_time_s=5.0)
    def monitor_once():
        trades = client.get_open_trades()
        for trade in trades:
            symbol = trade['symbol']
            nominal_value = float(trade['nominalValue'])
            if not contract_values.get(symbol):
                contract_values[symbol] = 0.0
            contract_values[symbol] += nominal_value

    monitor_once()
    for k, v in contract_values.items():
        print(k, v)
        add_contract_value(k, v)
