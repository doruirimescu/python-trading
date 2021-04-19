from Trading.Live.Logger.logger import DataLogger
from Trading.Instrument.instrument import Instrument
from Trading.Candlechart.candleCsvWriter import CandleCsvWriter
from Trading.Live.Client.client import XTBLoggingClient

import argparse
import getpass

def getInstrument():
    parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
    parser.add_argument('-s', dest='symbol', type=str, required=True)
    parser.add_argument('-t', dest='timeframe', type=str, required=True)
    args = parser.parse_args()
    return Instrument(args.symbol, args.timeframe)

def readUsername():
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
