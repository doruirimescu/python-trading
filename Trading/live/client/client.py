from datetime import datetime
from exception_with_retry import exception_with_retry
from Trading.utils.time import get_datetime_now_cet
from Trading.utils.send_email import send_email_if_exception_occurs
from Trading.config.config import TIMEZONE

from Trading.instrument.instrument import Instrument
from Trading.instrument.timeframes import TIMEFRAME_TO_MINUTES


from XTBApi.api import Client as XTBClient
from Trading.live.logger.server_tester import *

from datetime import timedelta
import pytz
from typing import Optional, Tuple
from collections import namedtuple



# TODO: adjust sleep_time and retries to take into account composite functions
TradingTimes = namedtuple("trading_times", ['from_t', 'to_t'])
Volume = namedtuple("volume", ['open_price', 'units'])


class LoggingClient:
    def __init__(self, client, server_tester):
        self._client = client
        self._server_tester = server_tester

    # @send_email_if_exception_occurs()
    # @exception_with_retry(n_retry=1, sleep_time_s=1)
    def get_last_n_candles_history(self, instrument: Instrument, N: int):
        if (not self._is_server_up):
            return None

        self._client.login()
        hist = self._client.get_lastn_candle_history(
            instrument.get_symbol_xtb(), TIMEFRAME_TO_MINUTES[instrument.timeframe] * 60, N)
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

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_all_symbols(self):
        self._client.login()
        symbols = self._client.get_all_symbols()
        self._client.logout()
        symbols = [s['symbol'] for s in symbols]
        # Should remove _4
        symbols = list(filter(lambda t: t[-2:] != "_4", symbols))
        return symbols

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=1, sleep_time_s=1)
    def get_profit_calculation(self, symbol, open_price, close_price, volume, cmd):
        # cmd = 0 for buy, 1 for sell
        self._client.login()
        response = self._client.get_profit_calculation(symbol, cmd, volume, open_price, close_price)
        self._client.logout()
        return float(response['profit'])

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=1)
    def get_trading_hours_today_cet(self, symbol) -> Tuple[Optional[datetime], Optional[datetime]]:
        now = get_datetime_now_cet()
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
                return TradingTimes(from_date, to_date)
        return TradingTimes(None, None)

    def is_market_open(self, symbol: str) -> bool:
        from_t, to_t = self.get_trading_hours_today_cet(symbol)
        if from_t is None or to_t is None:
            return False
        time_now_cet = get_datetime_now_cet()
        if time_now_cet > from_t and time_now_cet < to_t:
            return True
        return False

    def is_market_closing_in_n_seconds(self, symbol: str, n_seconds: int) -> bool:
        from_t, to_t = self.get_trading_hours_today_cet(symbol)
        datetime_now = get_datetime_now_cet()
        dt_to_closing = to_t - datetime_now
        if dt_to_closing.total_seconds() < n_seconds:
            return True
        return False

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_current_price(self, symbol):
        now = datetime.now()
        ts = now.timestamp()
        self._client.login()
        prices = self._client.get_tick_prices([symbol], ts)
        self._client.logout()
        return (prices['quotations'][0]['bid'], prices['quotations'][0]['ask'])

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def _is_server_up(self):
        test = self._server_tester.test()
        return test.is_server_up

    # This can fail sometimes ex USDRUB
    def get_symbol(self, symbol):
        self._client.login()
        response = self._client.get_symbol(symbol)
        self._client.logout()
        return response

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_open_trade_profit(self, trans_id):
        self._client.login()
        response = self._client.get_trade_profit(trans_id)
        self._client.logout()
        return response

    def get_margin_trade(self, symbol, volume):
        self._client.login()
        response = self._client.get_margin_trade(symbol, volume)
        self._client.logout()
        return response['margin']


    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_closed_trade_profit(self, position):
        self._client.login()
        response = self._client.get_trades_history(0, 0)
        self._client.logout()
        for trade in response:
            if trade['position'] == position:
                return trade['profit']
        return None

    @send_email_if_exception_occurs()
    def calculate_volume_bid(self, symbol: str, cash_amount: int) -> Volume:
        """Calculates the transaction volume for given cash amount.
           Cash amount should be expressed in the correct currency,
           calculated by currency = get_symbol(symbol)['currency']
        """
        data = self.get_symbol(symbol)
        open_price = data['ask']
        contract_size = data['contractSize']
        currency = data['currency']
        if data['categoryName'] == 'FX':
            print(f"Calculating forex volume, with prices in {currency}")
            volume = round(cash_amount / contract_size, 2)
        else:
            print(f"Calculating stock volume, with prices in {currency}")
            volume = int(cash_amount/open_price)
        print(f"Calculated volume {volume} for symbol {symbol}")
        return Volume(open_price, volume)

    def get_server_time(self):
        self._client.login()
        response = self._client.get_server_time()
        self._client.logout()
        return response

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_top_ten_biggest_swaps(self):
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
        sorted_list = sorted(symbol_list, key=operator.itemgetter(2, 1), reverse=True)

        # for sym, sl, ss in sorted_list[0:10]:
        #     print("Pair:\t{}\tSwap long:{:>10}\tSwap short:{:>10}".format(
        #                         sym, sl, ss))
        self._client.logout()
        return sorted_list


class TradingClient(LoggingClient):
    def __init__(self, client, server_tester):
        super().__init__(client, server_tester)

    @send_email_if_exception_occurs()
    # @exception_with_retry(n_retry=10, sleep_time_s=6)
    def buy(self, symbol, volume):
        """Opens a buy trade on the XTB trading platform. Returns the id of the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="buy", symbol=symbol, volume=volume)
        self._client.logout()
        return response

    @send_email_if_exception_occurs()
    # @exception_with_retry(n_retry=10, sleep_time_s=6)
    def sell(self, symbol, volume):
        """Opens a sell trade on the XTB trading platform. Returns the trade id
        """
        self._client.login()
        response = self._client.open_trade(mode="sell", symbol=symbol, volume=volume)
        self._client.logout()
        return response

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=4, sleep_time_s=1)
    def close_trade(self, trade_id):
        """Closes a trade by trade id
        """
        self._client.login()
        response = self._client.close_trade_fix(trade_id)
        self._client.logout()

    @send_email_if_exception_occurs()
    # @exception_with_retry(n_retry=10, sleep_time_s=6)
    def close_trade_fix(self, order):
        self._client.login()
        response = self._client.close_trade_fix(order)
        self._client.logout()

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_open_trades(self):
        self._client.login()
        response = self._client.get_trades()
        self._client.logout()
        return response

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_total_forex_open_trades_profit_and_swap(self):
        self._client.login()
        open_trades = self._client.get_trades()

        total_profit = 0.0
        total_swap = 0.0
        text_message = ""
        data = list()
        for trade in open_trades:
            symbol = trade['symbol']
            symbol_info = self._client.get_symbol(symbol)
            if symbol_info['categoryName'] == 'FX':
                pair_profit = float(trade['profit'])
                pair_swap = float(trade['storage'])
                if pair_swap == 0.0:
                    continue
                data.append((symbol, pair_swap))
                total_profit += pair_profit
                total_swap += pair_swap
                text_message += "Pair:\t{}\tProfit:{:>10}\tSwap:{:>10}".format(symbol, pair_profit, pair_swap)
                text_message += "\n"
        self._client.logout()

        total_profit = round(total_profit, 5)
        return (total_profit, total_swap, text_message, data)

    @send_email_if_exception_occurs()
    @exception_with_retry(n_retry=10, sleep_time_s=6)
    def get_swaps_of_forex_open_trades(self):
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


class XTBLoggingClient(LoggingClient):
    def __init__(self, uname, pwd, mode="demo", logging=False):
        client = XTBClient(uname, pwd, mode, logging)
        server_tester = ServerTester(client)
        super().__init__(client, server_tester)


class XTBTradingClient(TradingClient):
    def __init__(self, uname, pwd, mode="demo", should_log=False):
        client = XTBClient(uname, pwd, mode, should_log)
        server_tester = ServerTester(client)
        super().__init__(client, server_tester)
