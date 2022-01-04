from Trading.Live.Logger.logger import DataLogger
from Trading.Instrument.instrument import Instrument
from Trading.Candlechart.candleCsvWriter import CandleCsvWriter
from Trading.Live.Client.client import XTBLoggingClient

import argparse
import getpass

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
        Instrument: Instrument for which the logging is performed.
    """
    parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
    parser.add_argument('-s', dest='symbol', type=str, required=True)
    parser.add_argument('-t', dest='timeframe', type=str, required=True)
    args = parser.parse_args()
    return Instrument(args.symbol, args.timeframe)

def readUsername():
    """Reads the username from a file called username.txt.

    Returns:
        str: username
    """
    f = open("username.txt", "r")
    lines = f.readlines()
    username = lines[0].rstrip()
    f.close()
    return username

if __name__ == '__main__':
    username = readUsername()
    instrument = getInstrument()
    csvwriter = CandleCsvWriter(instrument, "data/")
    xtb_client = XTBLoggingClient(username, getpass.getpass())

    with DataLogger(instrument, xtb_client, csvwriter, 100) as data_logger:
        print("Started logging")
        data_logger.mainLoop()
