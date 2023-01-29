from Trading.Live.Client.client import XTBTradingClient
from Trading.Live.Email.send_email import send_email

from dotenv import load_dotenv
from datetime import datetime
import os
from Trading.Live.Logger.ticker import Ticker
import logging


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

    # Get profit and swap of current trades
    # total_profit, total_swap = client.getTotalForexOpenTradesProfitAndSwap()
    # print("Total profit", total_profit)
    # print("Total swap", total_swap)

    biggest_swaps = client.getTopTenBiggestSwaps()
    print(biggest_swaps)
    # subject = "Top ten biggest swaps as of " + str(datetime.now())
    # body = str(biggest_swaps)
    # recipients = ["dorustefan.irimescu@gmail.com"]
    # send_email(subject, body, recipients)

    # open_trade_swaps = client.getSwapsOfForexOpenTrades()
    # print(open_trade_swaps)

    # for symbol, swap in open_trade_swaps:
    #     if swap < 0.0:
    #         subject = "Swap has gone negative for " + symbol
    #         body = f"Symbol: {symbol} Swap: {str(swap)} Date:{str(datetime.now())}"
    #         recipients = ["dorustefan.irimescu@gmail.com"]
    #         send_email(subject, body, recipients)
