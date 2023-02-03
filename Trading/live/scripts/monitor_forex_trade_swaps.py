from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE, MONITOR_FOREX_TRADE_SWAPS_ONCE
from Trading.live.alert.alert import get_total_swap_of_open_forex_trades_report, is_symbol_price_below_value, is_symbol_price_below_last_n_intervals_low

from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from time import sleep


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

    open_trade_swaps = client.get_swaps_of_forex_open_trades()
    MAIN_LOGGER.info("Open trade swaps: " + str(open_trade_swaps))

    @exception_with_retry(n_retry=10, sleep_time_s=5.0)
    def monitor_once():
        subject = "Daily swap report " + str(datetime.now())
        body = get_total_swap_of_open_forex_trades_report(client)
        send_email(subject, body)
        MAIN_LOGGER.info(body)

    if MONITOR_FOREX_TRADE_SWAPS_ONCE == "True":
        monitor_once()
    else:
        while True:
            hour_now = datetime.now().hour
            minute_now = datetime.now(). minute
            if hour_now == 7:
                # Each morning at 7 am
                monitor_once()
            sleep(3600)
