from Trading.Live.Client.client import XTBTradingClient
from Trading.Live.Trader.trader import Trader
from Trading.Instrument.instrument import Instrument
from Trading.Live.InvestingAPI.investing_technical import TechnicalAnalyzer
from dotenv import load_dotenv
import time
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

    total_profit, total_swap = client.getTotalForexOpenTradesProfitAndSwap()
    print("Total profit", total_profit)
    print("Total swap", total_swap)
