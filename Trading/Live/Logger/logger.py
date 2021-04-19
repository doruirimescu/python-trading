import getpass

from Trading.Live.Client.client import XTBLoggingClient, Client
from datetime import datetime
from datetime import timedelta

from Trading.Candlechart.candle import Candle

from Trading.Live.InvestingAPI.investing_candlestick import PatternAnalyzer
from Trading.Live.InvestingAPI.investing_candlestick import PatternAnalysis
from Trading.Live.InvestingAPI.investing_candlestick import PatternReliability

from Trading.Live.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry

from Trading.Live.InvestingAPI.investing_technical import *

from Trading.Live.Logger.ticker import Ticker
from Trading.Instrument.instrument import Instrument
from Trading.Instrument.timeframes import *
from Trading.Candlechart.candleCsvWriter import CandleCsvWriter

import time

# objects used to be mocked: CandleCsvWriter, Client, TechnicalAnalyzer, PatternAnalyzer
class DataLogger:
    def __init__(self, instrument: Instrument, client: Client, csvwriter: CandleCsvWriter, windowsize = 20):
        self._instrument = instrument
        self._csv_writer = csvwriter
        self._client = client

        # # Get last WINDOW_SIZE candles
        hist = self._getLastNCandleHistory(self._instrument, windowsize)

        self.candle_dictionary = dict()

        for i in range(len(hist['open'])):
            open = hist['open'][i]
            high = hist['high'][i]
            low = hist['low'][i]
            close = hist['close'][i]
            date = hist['date'][i]

            candle = Candle(open, high, low, close, date)
            candle.setTechnicalAnalysis("")
            candle.setPatternAnalysis(PatternAnalysis())
            self.candle_dictionary[date] = candle

        self._updatePatterns()

    def _getLastNCandleHistory(self, instrument, N):
        return self._client.getLastNCandleHistory(instrument, N)

    def _getPatternAnalysis(self):
        i = PatternAnalyzer()
        ewr = ExceptionWithRetry(i.analyse, 10, 1.0)
        analysis = ewr.run( [self._symbolToInvesting(), self._instrument.timeframe] )
        return analysis

    def _getTechnicalAnalysis(self):
        inv_tech = TechnicalAnalyzer()
        ewr = ExceptionWithRetry(inv_tech.analyse, 10, 1.0)
        analysis = ewr.run([self._symbolToInvesting(), self._instrument.timeframe])
        return analysis

    def mainLoop(self):
        ticker = Ticker(self._instrument.timeframe)
        while True:
            time.sleep(1)
            if ticker.tick():
                self._loopOnce()

    def _loopOnce(self):
        # 1. Get the latest candle
        ohlct = self._getLastNCandleHistory(self._instrument, 1)

        open    = ohlct['open'][0]
        high    = ohlct['high'][0]
        low     = ohlct['low'][0]
        close   = ohlct['close'][0]
        date    = ohlct['date'][0]

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

            # 5. Print oldest candle to file
            self._csv_writer.writeCandle(oldest_candle)

    def _updatePatterns(self):
        # # Get last candlestick patterns and match to candles
        candle_patterns = self._getPatternAnalysis()
        if candle_patterns is None:
            print("None candle patterns")
            return
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
        if self._instrument.symbol == "BITCOIN":
            return "BTCUSD"
        elif self._instrument.symbol == "ETHEREUM":
            return "ETHUSD"
        else:
            return self._instrument.symbol

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Write remaining candles to file!
        for key in self.candle_dictionary:
            self._csv_writer.writeCandle(self.candle_dictionary[key])
        print("Stopped logging")
