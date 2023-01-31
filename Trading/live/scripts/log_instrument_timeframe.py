from Trading.live.logger.logger import DataLogger
from Trading.candlechart.candleCsvWriter import CandleCsvWriter
from Trading.live.client.client import XTBLoggingClient
from Trading.utils.argument_parser import get_instrument

from dotenv import load_dotenv
import os

"""This script is used to log the candles and technical analysis of an instrument.
The username is read from a file called username.txt. The password needs to be given by the user when
prompted.

Make an xtb.com demo account. The username is the numerical code which appears next to DEMO
on the xstation platform when you are logged in.

Currently this script works only with investing.com symbols.
"""



if __name__ == '__main__':
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    instrument = get_instrument()
    csvwriter = CandleCsvWriter(instrument, "data/")
    xtb_client = XTBLoggingClient(username, password)

    with DataLogger(instrument, xtb_client, csvwriter, 100) as data_logger:
        print("Started logging")
        data_logger.mainLoop()
