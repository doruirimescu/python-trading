from Trading.Live.Logger.logger import DataLogger
from Trading.Instrument.instrument import Instrument
import argparse

parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
parser.add_argument('-s', dest='symbol', type=str, required=True)
parser.add_argument('-t', dest='timeframe', type=str, required=True)
args = parser.parse_args()

f = open("username.txt", "r")
lines = f.readlines()
username = lines[0].rstrip()
f.close()
instrument = Instrument(args.symbol, args.timeframe)

with DataLogger(instrument, username, "data/", 100) as data_logger:
    print("Started logging")
    data_logger.mainLoop()
