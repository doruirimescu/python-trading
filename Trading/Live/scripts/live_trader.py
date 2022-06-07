from Trading.Live.Client.client import XTBTradingClient
from Trading.Live.Trader.trader import Trader
from Trading.Instrument.instrument import Instrument
from Trading.Live.InvestingAPI.investing_technical import TechnicalAnalyzer
from dotenv import load_dotenv
import time
import os
import argparse
from Trading.Live.Logger.ticker import Ticker
import logging


def getInstrument():
    """Creates an instrument object from the command line arguments.

    Returns:
        Instrument: Instrument for which the logging is performed.
    """
    parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
    parser.add_argument('-s', dest='symbol', type=str, required=True)
    parser.add_argument('-t', dest='timeframe', type=str, required=True)
    args = parser.parse_args()
    return Instrument(args.symbol, args.timeframe)


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main Logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    TRADER_LOGGER = logging.getLogger('Trader')
    TRADER_LOGGER.setLevel(logging.DEBUG)
    TRADER_LOGGER.propagate = True

    TICKER_LOGGER = logging.getLogger('Ticker')
    TICKER_LOGGER.setLevel(logging.DEBUG)
    TICKER_LOGGER.propagate = True

    STRATEGY_LOGGER = logging.getLogger('Strategy')
    STRATEGY_LOGGER.setLevel(logging.DEBUG)
    STRATEGY_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = 'demo'
    client = XTBTradingClient(username, password, mode, False)

    instrument = getInstrument()
    technical_analyzer = TechnicalAnalyzer()
    trader = Trader(client=client, instrument=instrument, technical_analyzer=technical_analyzer)

    ticker = Ticker(instrument.timeframe)

    while True:
        time.sleep(1)
        if ticker.tick():
            trader.trade()
