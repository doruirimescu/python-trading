from Trading.Live.Client.client import XTBTradingClient
from Trading.Live.Email.send_email import send_email

from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from time import sleep


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main Logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, mode, False)

    open_trade_swaps = client.getSwapsOfForexOpenTrades()
    MAIN_LOGGER.info("Open trade swaps: " + str(open_trade_swaps))

    while True:
        hour_now = datetime.now().hour
        minute_now = datetime.now(). minute

        if hour_now == 7:
            # Each morning at 7 am
            for symbol, swap in open_trade_swaps:
                if swap < 0.0:
                    subject = "Swap has gone negative for " + symbol
                    body = f"Symbol: {symbol} Swap: {str(swap)} Date:{str(datetime.now())}"
                    recipients = ["dorustefan.irimescu@gmail.com"]
                    send_email(subject, body, recipients)

            total_profit, total_swap, text_message = client.getTotalForexOpenTradesProfitAndSwap()
            subject = "Daily swap report" + str(datetime.now())
            body = text_message + f"\nTotal profit: {str(total_profit)} Total swap: {str(total_swap)}"
            recipients = ["dorustefan.irimescu@gmail.com"]
            send_email(subject, body, recipients)
            MAIN_LOGGER.info(body)
            sleep(3600)
