from abc import ABC, abstractmethod
from datetime import datetime


from Trading.Instrument.instrument import Instrument
from Trading.Instrument.timeframes import TIMEFRAME_TO_MINUTES

from XTBApi.api import Client as XTBClient
from Trading.Live.Logger.server_tester import *


class LoggingClient(ABC):
    @abstractmethod
    def __init__(self, uname=0, pwd=0, mode=0):
        pass

    @abstractmethod
    def getLastNCandleHistory(self):
        pass


class TradingClient(ABC):
    @abstractmethod
    def __init__(self, uname=0, pwd=0, mode=0):
        pass

    @abstractmethod
    def buy(self, instrument, volume):
        pass

    @abstractmethod
    def sell(self, instrument, volume):
        pass

    @abstractmethod
    def closeTrade(self, trade_id):
        pass


class XTBTradingClient():
    def __init__(self, uname, pwd, mode="demo", logging=False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def buy(self, instrument, volume):
        """Opens a buy trade on the XTB trading platform. Returns the id of the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="buy", symbol=instrument.symbol, volume=volume)
        self._client.logout()
        return response

    def sell(self, instrument, volume):
        """Opens a sell trade on the XTB trading platform. Returns the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="sell", symbol=instrument.symbol, volume=volume)
        self._client.logout()
        return response

    def closeTrade(self, trade_id):
        """Closes a trade by trade id
        """
        self._client.login()
        response = self._client.close_trade_fix(trade_id['order'])
        self._client.logout()


class XTBLoggingClient(LoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging=False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def getLastNCandleHistory(self, instrument: Instrument, N: int):
        if (not self._isServerUp):
            return None

        instrument.symbol = instrument.symbol
        self._client.login()
        hist = self._client.get_lastn_candle_history(
            instrument.symbol, TIMEFRAME_TO_MINUTES[instrument.timeframe] * 60, N)
        self._client.logout()

        open = list()
        high = list()
        low = list()
        close = list()
        date = list()

        for ohlct in hist:
            open.append(ohlct['open'])
            high.append(ohlct['high'])
            low.append(ohlct['low'])
            close.append(ohlct['close'])
            date.append(datetime.fromtimestamp(ohlct['timestamp']))
        return {'open': open, 'high': high, 'low': low, 'close': close, 'date': date}

    def _isServerUp(self):
        test = self._server_tester.test()
        return test.is_server_up
