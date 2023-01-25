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
        response = self._client.open_trade(mode="buy", symbol=instrument.getSymbolXTB(), volume=volume)
        self._client.logout()
        return response

    def sell(self, instrument, volume):
        """Opens a sell trade on the XTB trading platform. Returns the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="sell", symbol=instrument.getSymbolXTB(), volume=volume)
        self._client.logout()
        return response

    def closeTrade(self, trade_id):
        """Closes a trade by trade id
        """
        self._client.login()
        response = self._client.close_trade_fix(trade_id['order'])
        self._client.logout()

    def getOpenTrades(self):
        self._client.login()
        response = self._client.get_trades()
        self._client.logout()
        return response

    def getSymbol(self, symbol):
        self._client.login()
        response = self._client.get_symbol(symbol)
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

    def _isServerUp(self):
        test = self._server_tester.test()
        return test.is_server_up
