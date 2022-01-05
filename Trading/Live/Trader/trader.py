from Trading.Algo.Strategy.strategy import *
from Trading.Live.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry
from Trading.Live.Client.client import LoggingClient
from Trading.Instrument.instrument import Instrument
from Trading.Live.InvestingAPI.investing_technical import *

class Trader:
    def __init__(self, instrument: Instrument, client: TradingClient, technical_analyzer):

        self._instrument = instrument
        self._client = client
        self._technical_analyzer = technical_analyzer

    def _getTechnicalAnalysis(self):
        ewr = ExceptionWithRetry(self._technical_analyzer.analyse, 10, 1.0)
        analysis = ewr.run([self._symbolToInvesting(), self._instrument.timeframe])
        return analysis

    def _symbolToInvesting(self):
        if self._instrument.symbol == "BITCOIN":
            return "BTCUSD"
        elif self._instrument.symbol == "ETHEREUM":
            return "ETHUSD"
        else:
            return self._instrument.symbol
