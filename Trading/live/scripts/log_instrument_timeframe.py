from Trading.live.Logger.logger import DataLogger
from Trading.instrument.instrument import instrument
from Trading.candlechart.candleCsvWriter import CandleCsvWriter
from Trading.live.Client.client import XTBLoggingClient
from dotenv import load_dotenv
import os
import argparse

"""This script is used to log the candles and technical analysis of an instrument.
The username is read from a file called username.txt. The password needs to be given by the user when
prompted.

Make an xtb.com demo account. The username is the numerical code which appears next to DEMO
on the xstation platform when you are logged in.

Currently this script works only with investing.com symbols.
"""


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
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    instrument = getInstrument()
    csvwriter = CandleCsvWriter(instrument, "data/")
    xtb_client = XTBLoggingClient(username, password)

    with DataLogger(instrument, xtb_client, csvwriter, 100) as data_logger:
        print("Started logging")
        data_logger.mainLoop()
