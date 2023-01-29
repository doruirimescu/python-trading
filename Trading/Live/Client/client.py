from abc import ABC, abstractmethod
from datetime import datetime

from Trading.Utils.time import getDatetimeNowCet

from Trading.Instrument.instrument import Instrument
from Trading.Instrument.timeframes import TIMEFRAME_TO_MINUTES

from XTBApi.api import Client as XTBClient
from XTBApi.api import Transaction
from Trading.Live.Logger.server_tester import *

from datetime import timedelta
import pytz

from collections import namedtuple

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


TradingTimes = namedtuple("trading_times", ['from_t', 'to_t'])

class XTBLoggingClient(LoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging=False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def getLastNCandleHistory(self, instrument: Instrument, N: int):
        if (not self._isServerUp):
            return None

        self._client.login()
        hist = self._client.get_lastn_candle_history(
            instrument.getSymbolXTB(), TIMEFRAME_TO_MINUTES[instrument.timeframe] * 60, N)
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

    def getAllSymbols(self):
        self._client.login()
        symbols = self._client.get_all_symbols()
        self._client.logout()
        return [s['symbol'] for s in symbols]

    def getProfitCalculation(self, symbol, open_price, close_price, volume, cmd):
        # cmd = 0 for buy, 1 for sell
        self._client.login()
        response = self._client.get_profit_calculation(symbol, cmd, volume, open_price, close_price)
        self._client.logout()
        return float(response['profit'])

    def getTradingHoursTodayCET(self, symbol):
        now = datetime.now()
        weekday = now.weekday() + 1
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self._client.login()
        response = self._client.get_trading_hours([symbol])[0]
        self._client.logout()
        for t in response['trading']:
            if t['day'] == weekday:
                from_t_s = t['fromT']
                to_t_s = t['toT']

                from_td = timedelta(seconds=from_t_s)
                to_td = timedelta(seconds=to_t_s)

                from_date = today + from_td
                to_date = today + to_td

                to_date = to_date.replace(tzinfo=pytz.timezone('Europe/Berlin'))
                from_date = from_date.replace(tzinfo=pytz.timezone('Europe/Berlin'))
                return TradingTimes(from_date, to_date)
        return TradingTimes(None, None)

    def isMarketOpen(self, symbol: str) -> bool:
        from_t, to_t = self.getTradingHoursTodayCET(symbol)
        if from_t is None or to_t is None:
            return False
        time_now_cet = getDatetimeNowCet()
        if time_now_cet > from_t and time_now_cet < to_t:
            return True
        return False

    def isMarketClosingInNSeconds(self, symbol: str, n_seconds: int) -> bool:
        from_t, to_t = self.getTradingHoursTodayCET(symbol)
        datetime_now = getDatetimeNowCet()
        dt_to_closing = to_t - datetime_now
        if dt_to_closing.total_seconds() < n_seconds:
            return True
        return False

    def getCurrentPrice(self, symbol):
        now = datetime.now()
        ts = now.timestamp()
        self._client.login()
        prices = self._client.get_tick_prices([symbol], ts)
        self._client.logout()
        return (prices['quotations'][0]['bid'], prices['quotations'][0]['ask'])

    def _isServerUp(self):
        test = self._server_tester.test()
        return test.is_server_up

    def getSymbol(self, symbol):
        self._client.login()
        response = self._client.get_symbol(symbol)
        self._client.logout()
        return response

    def getOpenTradeProfit(self, trans_id):
        self._client.login()
        response = self._client.get_trade_profit(trans_id)
        self._client.logout()
        return response

    def getClosedTradeProfit(self, position):
        self._client.login()
        response = self._client.get_trades_history(0, 0)
        self._client.logout()
        for trade in response:
            if trade['position'] == position:
                return trade['profit']
        return None


class XTBTradingClient(XTBLoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging=False):
        self._client = XTBClient(uname, pwd, mode, logging)
        self._server_tester = ServerTester(self._client)

    def buy(self, symbol, volume):
        """Opens a buy trade on the XTB trading platform. Returns the id of the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="buy", symbol=symbol, volume=volume)
        self._client.logout()
        return response

    def sell(self, symbol, volume):
        """Opens a sell trade on the XTB trading platform. Returns the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="sell", symbol=symbol, volume=volume)
        self._client.logout()
        return response

    def closeTrade(self, trade_id):
        """Closes a trade by trade id
        """
        self._client.login()
        response = self._client.close_trade_fix(trade_id['order'])
        self._client.logout()

    def close_by_trade(self, trade):
        self._client.login()
        response = self._client.close_trade(trade)
        self._client.logout()

    def close_trade_fix(self, order):
        self._client.login()
        response = self._client.close_trade_fix(order)
        self._client.logout()

    def getOpenTrades(self):
        self._client.login()
        response = self._client.get_trades()
        self._client.logout()
        return response

    def getTotalForexOpenTradesProfitAndSwap(self):
        self._client.login()
        open_trades = self._client.get_trades()

        total_profit = 0.0
        total_swap = 0.0
        text_message = ""
        for trade in open_trades:
            symbol = trade['symbol']
            symbol_info = self._client.get_symbol(symbol)
            if symbol_info['categoryName'] == 'FX':
                pair_profit = float(trade['profit'])
                pair_swap = float(trade['storage'])
                total_profit += pair_profit
                total_swap += pair_swap
                text_message += "Pair:\t{}\tProfit:{:>10}\tSwap:{:>10}".format(symbol, pair_profit, pair_swap)
                text_message += "\n"
        self._client.logout()

        total_profit = round(total_profit, 5)
        return (total_profit, total_swap, text_message)

    def getSwapsOfForexOpenTrades(self):
        self._client.login()
        open_trades = self._client.get_trades()
        symbol_list = list()
        for trade in open_trades:
            symbol = trade['symbol']
            symbol_info = self._client.get_symbol(symbol)
            if symbol_info['categoryName'] == 'FX':
                short_long = trade['cmd']
                if short_long == 0:
                    swap = symbol_info['swapLong']
                elif short_long == 1:
                    swap = symbol_info['swapShort']
                symbol_list.append((symbol, swap,))
        return symbol_list

    def getTopTenBiggestSwaps(self):
        self._client.login()
        all_symbols = self._client.get_all_symbols()

        symbol_list = list()
        for symbol in all_symbols:
            if symbol['categoryName'] == 'FX':
                sym = symbol['symbol']
                sl = symbol['swapLong']
                ss = symbol['swapShort']
                symbol_list.append((sym, sl, ss,))
        import operator
        sorted_list = sorted(symbol_list, key=operator.itemgetter(2,1), reverse=True)

        for sym, sl, ss in sorted_list[0:10]:
            print("Pair:\t{}\tSwap long:{:>10}\tSwap short:{:>10}".format(
                                sym, sl, ss))
        self._client.logout()
        return sorted_list
