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

# class YahooFinanceLoggingCient(LoggingClient):
#     def __init__(self):
#         print("No init required")

#     def getLastNCandleHistory(self, instrument: Instrument, N: int):

#         ticker = yf.Ticker(SYMBOL_TO_X[instrument.symbol][SYMBOL_YFINANCE_INDEX])

#         start_time = datetime.now() - self._getTimeDelta(instrument.timeframe, N)
#         end_time = datetime.now()

#         timeframe = TIMEFRAME_TO_YFINANCE[instrument.timeframe]
#         data = ticker.history(interval=timeframe, start= start_time, end= end_time)

#         second_last_date = data.index[len(data)-2]
#         last_date = data.index[len(data)-1]
#         time_difference_minutes = (last_date - second_last_date).total_seconds()/60

#         if time_difference_minutes < TIMEFRAME_TO_MINUTES[instrument.timeframe]:
#             print("Last candle is not finished yet")
#             data.drop(data.tail(1).index, inplace=True)

#         data = data.tail(N)

#         date = list()
#         for dat in data.index:
#             print(dateToTimezone(dat))
#             date.append(dateToTimezone(dat))

#         open    = data['Open']
#         high    = data['High']
#         low     = data['Low']
#         close   = data['Close']

#         print(data)
#         return {'open':open, 'high':high, 'low':low, 'close':close, 'date': date}

#     def _getTimeDelta(self, timeframe, N):
#         n_minutes = max(5, TIMEFRAME_TO_MINUTES[timeframe] * (N+1))
#         return timedelta(minutes= n_minutes)
# def dateToTimezone(date, timezone="UTC"):
#     if date.tzinfo == None:
#         new_date = pytz.timezone(timezone).localize(date)
#         return new_date
#     else:
#         return date.astimezone(timezone)

#! Use only centralized market instruments, otherwise there will be a large variation in
class XTBLoggingClient(LoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging = False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def getLastNCandleHistory(self, instrument: Instrument, N: int):
        if (not self._isServerUp):
            return None

        instrument.symbol = SYMBOL_TO_X[instrument.symbol][SYMBOL_XTB_INDEX]
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
