from abc import ABC
from datetime import datetime, timedelta, timezone

import yfinance as yf
from pandas import DataFrame

from Trading.Instrument.instrument import Instrument
from Trading.Instrument.timeframes import TIMEFRAME_TO_MINUTES
from Trading.Instrument.timeframes import TIMEFRAME_TO_YFINANCE

from Trading.Instrument.symbol_investing_to_x import SYMBOL_TO_X, SYMBOL_YFINANCE_INDEX, SYMBOL_XTB_INDEX
import pytz

from XTBApi.api import Client as XTBClient
from Trading.Live.Logger.server_tester import *

class LoggingClient(ABC):
    def __init__(self, uname=0, pwd=0, mode=0):
        pass

    def getLastNCandleHistory(self):
        pass

#! Use only centralized market instruments, otherwise there will be a large variation in
class XTBLoggingClient(LoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging = False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def getLastNCandleHistory(self, instrument: Instrument, N: int):
        if (not self._isServerUp):
            return None

        instrument.symbol = instrument.symbol
        self._client.login()
        hist = self._client.get_lastn_candle_history(instrument.symbol, TIMEFRAME_TO_MINUTES[instrument.timeframe] * 60, N)
        self._client.logout()

        open    = list()
        high    = list()
        low     = list()
        close   = list()
        date    = list()

        for ohlct in hist:
            open.append(ohlct['open'])
            high.append(ohlct['high'])
            low.append(ohlct['low'])
            close.append(ohlct['close'])
            date.append(datetime.fromtimestamp(ohlct['timestamp']))
        return {'open':open, 'high':high, 'low':low, 'close':close, 'date': date}

    def _isServerUp(self):
        test = self._server_tester.test()
        return test.is_server_up
