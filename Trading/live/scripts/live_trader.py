from Trading.live.client.client import XTBTradingClient
from Trading.live.Trader.trader import Trader
from Trading.instrument.instrument import instrument
from Trading.live.investing_api.investing_technical import technical_analyzer
from dotenv import load_dotenv
import time
import os
import argparse
from Trading.live.logger.ticker import Ticker
import logging


def getInstrument():
    """Creates an instrument object from the command line arguments.

    Returns:
        instrument: instrument for which the logging is performed.
    """
    parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
    parser.add_argument('-s', dest='symbol', type=str, required=True)
    parser.add_argument('-t', dest='timeframe', type=str, required=True)
    args = parser.parse_args()
    return instrument(args.symbol, args.timeframe)


if __name__ == '__main__':
    # TODO: use optimal risk management for volume calculation
    # TODO: Try to aim for 50 50 trades, so put stop loss and take profit very close
    # TODO: to current price, such that every random fluctuation in either side will trigger
    # TODO: Scale accordingly, that the take profit lie inside of 1 standard deviation
    # TODO: of last price swings.

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    TRADER_LOGGER = logging.getLogger('Trader')
    TRADER_LOGGER.setLevel(logging.DEBUG)
    TRADER_LOGGER.propagate = True

    TICKER_LOGGER = logging.getLogger('Ticker')
    TICKER_LOGGER.setLevel(logging.INFO)
    TICKER_LOGGER.propagate = True

    STRATEGY_LOGGER = logging.getLogger('strategy')
    STRATEGY_LOGGER.setLevel(logging.DEBUG)
    STRATEGY_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = 'demo'
    client = XTBTradingClient(username, password, mode, False)

    instrument = getInstrument()
    technical_analyzer = technical_analyzer()
    trader = Trader(client=client, instrument=instrument, technical_analyzer=technical_analyzer)

    ticker = Ticker(instrument.timeframe)

    while True:
        time.sleep(1)
        if ticker.tick():
            trader.trade()
