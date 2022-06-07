from Trading.Algo.Strategy.strategy import *
from Trading.Live.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry
from Trading.Live.Client.client import TradingClient
from Trading.Instrument.instrument import Instrument
from Trading.Live.InvestingAPI.investing_technical import *
import logging


class Trader:
    '''
        Trader uses a client and a technical analyzer in order to decide what to do.
        It processes one trade at a time.
        It places a trade according to the decision.
        It also stops the current trade.
    '''

    def __init__(self, instrument: Instrument, client: TradingClient, technical_analyzer):

        self._instrument = instrument
        self._client = client
        self._technical_analyzer = technical_analyzer
        self.previous_analysis = None
        self.current_trade = None
        self.LOGGER = logging.getLogger('Trader')
        self.LOGGER.info("Create trader")

    def _getTechnicalAnalysis(self):
        ewr = ExceptionWithRetry(self._technical_analyzer.analyse, 10, 1.0)
        analysis = ewr.run([self._instrument])
        return analysis

    def trade(self):
        if self.previous_analysis is None:
            self.previous_analysis = self._getTechnicalAnalysis()
            self.LOGGER.info("Initialized previous_analysis")
            return
        current_analysis = self._getTechnicalAnalysis()
        action = decideAction(self.previous_analysis, current_analysis)
        self.previous_analysis = current_analysis
        print(action)

        if action == Action.NO:
            self.LOGGER.info("No action shall be taken")
        elif action == Action.BUY and self.current_trade is None:
            self.LOGGER.info("Client will buy. Should decide volume according to optimal risk")
            self.current_trade = self._client.buy(self._instrument, 0.01)
        elif action == Action.SELL and self.current_trade is None:
            self.LOGGER.info("Client will sell. Should decide volume according to optimal risk")
            self.current_trade = self._client.sell(self._instrument, 0.01)
        elif action == Action.STOP and self.current_trade is not None:
            self.LOGGER.info("Client will stop the current trade")
            self._client.closeTrade(self.current_trade)
            self.current_trade = None
