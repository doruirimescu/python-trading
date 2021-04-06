import argparse
import getpass

from XTBApi.api import Client
from datetime import datetime
from datetime import timedelta

from Trading.Candlechart.candle import Candle
from Trading.Candlechart.candleCsvWriter import CandleCsvWriter

from Trading.Live.InvestingAPI.investing_candlestick import PatternAnalyzer
from Trading.Live.InvestingAPI.investing_candlestick import PatternAnalysis
from Trading.Live.InvestingAPI.investing_candlestick import PatternReliability

from Trading.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry

from Trading.Live.InvestingAPI.investing_technical import *

from Trading.Logger.ticker import Ticker
from Trading.Live.InvestingAPI.timeframes import *

import time

class SessionInfo:
    def __init__(self):
        parser = argparse.ArgumentParser(description='Login to xtb.')
        parser.add_argument('-u', dest='username', type=str, required=True)
        args = parser.parse_args()
        self.username = args.username    # 11989223
        self.password = getpass.getpass()

class DataLogger:
    def __init__(self, symbol, timeframe, path = '/home/doru/personal/trading/data/', windowsize = 20, mode = "demo"):
        self._symbol = symbol
        self._timeframe = timeframe
        self._mode = mode
        self._path = path
        self._session_info = SessionInfo()

        self.csv_writer = CandleCsvWriter(self._symbol, self._timeframe, self._path)

        # # Get last WINDOW_SIZE candles
        hist = self._getLastNCandleHistory(self._symbol, self._timeframe, windowsize, self._mode)

        self.candle_dictionary = dict()
        for ohlct in hist:
            open    = ohlct['open']
            high    = ohlct['high']
            low     = ohlct['low']
            close   = ohlct['close']
            date    = datetime.fromtimestamp(ohlct['timestamp'])
            candle = Candle(open, high, low, close, date)
            candle.setTechnicalAnalysis("")
            candle.setPatternAnalysis(PatternAnalysis())
            self.candle_dictionary[date] = candle

        self._updatePatterns()

        for key in self.candle_dictionary:
            self.csv_writer.writeCandle(self.candle_dictionary[key])

    def _getLastNCandleHistory(self, symbol, timeframe, N, mode):
        client = Client()
        ewr = ExceptionWithRetry(client.login, 10, 1.0)
        ewr.run([self._session_info.username, self._session_info.password, mode])

        ewr = ExceptionWithRetry(client.get_lastn_candle_history, 10, 1.0)
        result = ewr.run( [symbol, TIMEFRAME_TO_MINUTES[self._timeframe] * 60, N] )

        ewr = ExceptionWithRetry(client.logout, 10, 1.0)
        ewr.run([])
        return result

    def _getPatternAnalysis(self):
        i = PatternAnalyzer()
        ewr = ExceptionWithRetry(i.analyse, 10, 1.0)
        analysis = ewr.run( [self._symbolToInvesting(), self._timeframe] )
        return analysis

    def _getTechnicalAnalysis(self):
        inv_tech = TechnicalAnalyzer()
        ewr = ExceptionWithRetry(inv_tech.analyse, 10, 1.0)
        analysis = ewr.run([self._symbolToInvesting(), self._timeframe])
        return analysis


    def mainLoop(self):
        ticker = Ticker(self._timeframe)
        while True:
            time.sleep(1)
            if ticker.tick():
                self._loopOnce()

    def _loopOnce(self):
        # 1. Get the latest candle
        ohlct = self._getLastNCandleHistory(self._symbol, self._timeframe, 1, self._mode)[0]
        open    = ohlct['open']
        high    = ohlct['high']
        low     = ohlct['low']
        close   = ohlct['close']
        date    = datetime.fromtimestamp(ohlct['timestamp'])

        if date not in self.candle_dictionary:
            # 2. If candle not in dictionary, update dictionary with new candle
            new_candle = Candle(open, high, low, close, date)

            # 3. Update candlestick tech
            technical_analysis = self._getTechnicalAnalysis()
            new_candle.setTechnicalAnalysis(technical_analysis.name)
            self.candle_dictionary[date] = new_candle
            print("New candle technical analysis: " + new_candle.getTechnicalAnalysis())

            # 4. Update candle pattern
            self._updatePatterns()

            # 4. Remove oldest candle from dict
            oldest_key = list(self.candle_dictionary.keys())[0]
            oldest_candle = self.candle_dictionary.pop(oldest_key)

            # 5. Print newest candle to file
            self.csv_writer.writeCandle(new_candle)

    def _updatePatterns(self):
        # # Get last candlestick patterns and match to candles
        candle_patterns = self._getPatternAnalysis()
        for pattern in candle_patterns:
            if pattern.date in self.candle_dictionary:
                current_pattern = self.candle_dictionary[pattern.date].getPatternAnalysis()
                print("Current_pattern")
                current_pattern.print()
                if pattern.isMoreReliableThan(current_pattern):
                    self.candle_dictionary[pattern.date].setPatternAnalysis(pattern)
                    print("Replacing old pattern with new candle pattern: " + pattern.pattern)
            else:
                print("Added new candle pattern")
                self.candle_dictionary[pattern.date].setPatternAnalysis(pattern)

    def _symbolToInvesting(self):
        if self._symbol is "BITCOIN":
            return "BTCUSD"
        elif self._symbol is "ETHEREUM":
            return "ETHUSD"
        else:
            return self._symbol

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("Stopped logging")
