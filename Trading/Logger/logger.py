import argparse
import getpass

from XTBApi.api import Client
from datetime import datetime
from datetime import timedelta

from Trading.Candlechart.candle import Candle
from Trading.Candlechart.candleCsvWriter import CandleCsvWriter

from Trading.InvestingAPI.investing_candlestick import PatternAnalyzer
from Trading.InvestingAPI.investing_candlestick import PatternAnalysis
from Trading.InvestingAPI.investing_candlestick import PatternReliability

from Trading.InvestingAPI.investing_technical import *

from Trading.Logger.ticker import Ticker
from Trading.InvestingAPI.timeframes import *

import time

class SessionInfo:
    def __init__(self):
        parser = argparse.ArgumentParser(description='Login to xtb.')
        parser.add_argument('-u', dest='username', type=str, required=True)
        args = parser.parse_args()
        self.username = args.username    # 11989223
        self.password = getpass.getpass()


class DataLogger:
    def __init__(self, symbol, timeframe, path = '/home/doru/personal/trading/data/', windowsize = 20):
        self.symbol = symbol
        self.timeframe = timeframe
        self.windowsize = windowsize
        self.path_ = path
        self.session_info = SessionInfo()

        self.csv_writer = CandleCsvWriter(self.symbol, self.timeframe, self.path_)

        # # Get last WINDOW_SIZE candles
        client = Client()
        client.login(self.session_info.username, self.session_info.password, mode ="demo")
        hist = client.get_lastn_candle_history(symbol, TIMEFRAME_TO_MINUTES[self.timeframe] * 60, self.windowsize)
        client.logout()

        self.candle_dictionary = dict()
        for h in hist:
            open    = h['open']
            high    = h['high']
            low     = h['low']
            close   = h['close']
            date    = datetime.fromtimestamp(h['timestamp'])
            candle = Candle(open, high, low, close, date)
            candle.setTechnicalAnalysis("")
            candle.setPatternAnalysis(PatternAnalysis())
            self.candle_dictionary[date] = candle

        self.__updatePatterns()

        for key in self.candle_dictionary:
            self.csv_writer.writeCandle(self.candle_dictionary[key])

    def mainLoop(self):
        ticker = Ticker(self.timeframe)
        while True:
            time.sleep(1)
            if ticker.tick():
                self.loopOnce()

    def loopOnce(self):
        # 1. Get the latest candle
        client = Client()
        client.login(self.session_info.username, self.session_info.password, mode ="demo")
        h = client.get_lastn_candle_history(self.symbol, TIMEFRAME_TO_MINUTES[self.timeframe] * 60, 1)[0]
        client.logout()

        open    = h['open']
        high    = h['high']
        low     = h['low']
        close   = h['close']
        date    = datetime.fromtimestamp(h['timestamp'])
        print(date)

        # 2. If candle not in dictionary, update dictionary with new candle
        new_candle = Candle(open, high, low, close, date)

        # 3. Update candlestick tech
        inv_tech = TechnicalAnalyzer()
        analysis = inv_tech.analyse(self.symbolToInvesting(), self.timeframe)
        new_candle.setTechnicalAnalysis(analysis.name)
        self.candle_dictionary[date] = new_candle
        print("New candle tech: "+ new_candle.getTechnicalAnalysis())

        # 4. Update candle pattern
        self.__updatePatterns()

        # 4. Remove oldest candle from dict
        oldest_key = list(self.candle_dictionary.keys())[0]
        oldest_candle = self.candle_dictionary.pop(oldest_key)

        # 5. Print newest candle to file
        self.csv_writer.writeCandle(new_candle)

    def __updatePatterns(self):
        # # Get last candlestick patterns and match to candles
        i = PatternAnalyzer()
        candle_patterns = i.analyse(self.symbolToInvesting(), self.timeframe)
        for pattern in candle_patterns:
            if pattern.date in self.candle_dictionary:
                current_pattern = self.candle_dictionary[pattern.date].getPatternAnalysis()
                if pattern.isMoreReliableThan(current_pattern):
                    self.candle_dictionary[pattern.date].setPatternAnalysis(pattern)
                    print("New candle pattern: " + pattern.pattern)

    def symbolToInvesting(self):
        if self.symbol is "BITCOIN":
            return "BTCUSD"
        elif self.symbol is "ETHEREUM":
            return "ETHUSD"
        else:
            return self.symbol

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("Stopped logging")
