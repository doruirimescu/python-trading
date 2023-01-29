from Trading.algo.strategy.strategy import *
from exception_with_retry import ExceptionWithRetry
from Trading.live.client.client import XTBTradingClient
from Trading.instrument.instrument import Instrument
from Trading.live.investing_api.investing_technical import *
import logging


class InvestingTrader:
    '''
        Trader uses a client and a technical analyzer in order to decide what to do.
        It processes one trade at a time.
        It places a trade according to the decision.
        It also stops the current trade.
    '''

    def __init__(self, instrument: Instrument, client: XTBTradingClient, technical_analyzer: InvestingTechnicalAnalyzer):

        self._instrument = instrument
        self._client = client
        self._technical_analyzer = technical_analyzer
        self.previous_analysis = None
        self.current_trade = None
        self.current_trade_type = None
        self.LOGGER = logging.getLogger('trader')
        self.LOGGER.info("Create trader")

    def _getTechnicalAnalysis(self):
        ewr = ExceptionWithRetry(self._technical_analyzer.analyse, 10, 1.0)
        analysis = ewr.run(self._instrument)
        return analysis

    def trade(self):
        if self.previous_analysis is None:
            self.previous_analysis = self._getTechnicalAnalysis()
            self.LOGGER.info("Initialized previous_analysis")
            return
        current_analysis = self._getTechnicalAnalysis()
        action = decide_action(self.previous_analysis, current_analysis)
        self.previous_analysis = current_analysis
        print(action)

        if action == Action.NO:
            self.LOGGER.info("No action shall be taken")
        elif action == Action.BUY:
            if self.current_trade is not None and self.current_trade_type == Action.SELL:
                self.close_trade()
            elif self.current_trade is None:
                self.LOGGER.info("client will buy. Should decide volume according to optimal risk")
                self.current_trade = self._client.buy(self._instrument, 0.01)
                self.current_trade_type = Action.BUY
        elif action == Action.SELL:
            if self.current_trade is not None and self.current_trade_type == Action.BUY:
                self.close_trade()
            elif self.current_trade is None:
                self.LOGGER.info("client will sell. Should decide volume according to optimal risk")
                self.current_trade = self._client.sell(self._instrument, 0.01)
                self.current_trade_type = Action.SELL
        elif action == Action.STOP and self.current_trade is not None:
            self.close_trade()

    def close_trade(self):
        self.LOGGER.info("client will close the current trade")
        try:
            self._client.close_trade(self.current_trade)
        except Exception as e:
            self.LOGGER.info(str(e))
        self.current_trade = None
        self.current_trade_type = None
