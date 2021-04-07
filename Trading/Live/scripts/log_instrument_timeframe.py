from Trading.Live.Logger.logger import DataLogger
import argparse

parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
parser.add_argument('-i', dest='instrument', type=str, required=True)
parser.add_argument('-t', dest='timeframe', type=str, required=True)
args = parser.parse_args()

f = open("username.txt", "r")
lines = f.readlines()
username = lines[0].rstrip()
f.close()

with DataLogger(args.instrument, args.timeframe, username, "data/", 100) as data_logger:
    print("Started logging")
    data_logger.mainLoop()
