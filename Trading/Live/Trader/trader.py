from Trading.algo.strategy.strategy import *
from exception_with_retry import ExceptionWithRetry
from Trading.Live.Client.client import TradingClient
from Trading.instrument.instrument import instrument
from Trading.Live.InvestingAPI.investing_technical import *
import logging


class Trader:
    '''
        Trader uses a client and a technical analyzer in order to decide what to do.
        It processes one trade at a time.
        It places a trade according to the decision.
        It also stops the current trade.
    '''

    def __init__(self, instrument: instrument, client: TradingClient, technical_analyzer):

        self._instrument = instrument
        self._client = client
        self._technical_analyzer = technical_analyzer
        self.previous_analysis = None
        self.current_trade = None
        self.current_trade_type = None
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
        elif action == Action.BUY:
            if self.current_trade is not None and self.current_trade_type == Action.SELL:
                self.closeTrade()
            elif self.current_trade is None:
                self.LOGGER.info("Client will buy. Should decide volume according to optimal risk")
                self.current_trade = self._client.buy(self._instrument, 0.01)
                self.current_trade_type = Action.BUY
        elif action == Action.SELL:
            if self.current_trade is not None and self.current_trade_type == Action.BUY:
                self.closeTrade()
            elif self.current_trade is None:
                self.LOGGER.info("Client will sell. Should decide volume according to optimal risk")
                self.current_trade = self._client.sell(self._instrument, 0.01)
                self.current_trade_type = Action.SELL
        elif action == Action.STOP and self.current_trade is not None:
            self.closeTrade()

    def closeTrade(self):
        self.LOGGER.info("Client will close the current trade")
        try:
            self._client.closeTrade(self.current_trade)
        except Exception as e:
            self.LOGGER.info(str(e))
        self.current_trade = None
        self.current_trade_type = None
