from Trading.candlechart.candle import Candle
from Trading.live.client.client import LoggingClient

from Trading.live.investing_api.investing_candlestick import PatternAnalyzer
from Trading.live.investing_api.investing_candlestick import PatternAnalysis

from exception_with_retry import ExceptionWithRetry

from Trading.live.investing_api.investing_technical import *

from Trading.live.logger.ticker import Ticker
from Trading.instrument.instrument import Instrument
from Trading.model.timeframes import *
from Trading.candlechart.candleCsvWriter import CandleCsvWriter

import time

# objects used to be mocked: CandleCsvWriter, LoggingClient, technical_analyzer, PatternAnalyzer


class DataLogger:
    def __init__(self, instrument: instrument, client: LoggingClient, csvwriter: CandleCsvWriter, windowsize=20):
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
            candle.set_technical_analysis("")
            candle.set_pattern_analysis(PatternAnalysis())
            self.candle_dictionary[date] = candle

        self._updatePatterns()

    def _getLastNCandleHistory(self, instrument, N):
        return self._client.get_last_n_candles_history(instrument, N)

    def _getPatternAnalysis(self):
        i = PatternAnalyzer()
        ewr = ExceptionWithRetry(i.analyse, 10, 1.0)
        analysis = ewr.run([self._instrument])
        return analysis

    def _getTechnicalAnalysis(self):
        inv_tech = InvestingTechnicalAnalyzer()
        ewr = ExceptionWithRetry(inv_tech.analyse, 10, 1.0)
        analysis = ewr.run([self._instrument])
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

        open = ohlct['open'][0]
        high = ohlct['high'][0]
        low = ohlct['low'][0]
        close = ohlct['close'][0]
        date = ohlct['date'][0]

        if date not in self.candle_dictionary:
            # 2. If candle not in dictionary, update dictionary with new candle
            new_candle = Candle(open, high, low, close, date)

            # 3. Update candlestick tech
            technical_analysis = self._getTechnicalAnalysis()
            new_candle.set_technical_analysis(technical_analysis.name)
            self.candle_dictionary[date] = new_candle
            print("New candle technical analysis: " + new_candle.get_technical_analysis())

            # 4. Update candle pattern
            self._updatePatterns()

            # 4. Remove oldest candle from dict
            oldest_key = list(self.candle_dictionary.keys())[0]
            oldest_candle = self.candle_dictionary.pop(oldest_key)

            # 5. Print oldest candle to file
            self._csv_writer.write_candle(oldest_candle)

    def _updatePatterns(self):
        # # Get last candlestick patterns and match to candles
        candle_patterns = self._getPatternAnalysis()
        if candle_patterns is None:
            print("None candle patterns")
            return
        for pattern in candle_patterns:
            if pattern.date in self.candle_dictionary:
                current_pattern = self.candle_dictionary[pattern.date].get_pattern_analysis()
                print("Current_pattern")
                current_pattern.print()
                if pattern.is_more_reliable_than(current_pattern):
                    self.candle_dictionary[pattern.date].set_pattern_analysis(pattern)
                    print("Replacing old pattern with new candle pattern: " + pattern.pattern)
            else:
                print("Added new candle pattern")
                self.candle_dictionary[pattern.date].set_pattern_analysis(pattern)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Write remaining candles to file!
        for key in self.candle_dictionary:
            self._csv_writer.write_candle(self.candle_dictionary[key])
        print("Stopped logging")
