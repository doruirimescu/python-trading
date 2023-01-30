from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import get_date_now_cet, get_datetime_now_cet
from Trading.algo.technical_analyzer.technical_analyzer import DailyBuyTechnicalAnalyzer
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.trade.trade import TradeType, Trade
from Trading.instrument.instrument import Instrument
from Trading.utils.write_to_file import write_json_to_file_named_with_today_date, read_json_from_file_named_with_today_date
from datetime import date
from typing import Dict

from dotenv import load_dotenv
import os
import logging
import time

trades_dict = dict()


def enter_trade(client: XTBTradingClient, contract_value: int,
                symbol: str, take_profit_percentage: float):
    date_now_cet = get_date_now_cet()
    todays_trade = Trade(date_=date_now_cet, type_=TradeType.BUY, contract_value=contract_value)
    trades_dict[date_now_cet] = todays_trade
    day_trading_analyzer = DailyBuyTechnicalAnalyzer(take_profit_percentage)

    if day_trading_analyzer.analyse(has_already_traded_instrument_today=False) == TechnicalAnalysis.STRONG_BUY:
        open_trade(client, todays_trade, contract_value)

    # Prepare to close trade
    IS_TRADE_CLOSED = False
    while not IS_TRADE_CLOSED:
        current_price = client.get_current_price(symbol)[0]
        is_market_closing_soon = client.is_market_closing_in_n_seconds(symbol, 90)
        should_close_trade = day_trading_analyzer.analyse(
                                True, todays_trade.open_price,
                                current_price, is_market_closing_soon) == TechnicalAnalysis.STRONG_SELL

        if should_close_trade:
            close_trade(client, todays_trade)
            todays_trade.close_price = current_price
            IS_TRADE_CLOSED = True
        time.sleep(1)


def open_trade(client: XTBTradingClient, trade: Trade, contract_value: int):
    # Calculate volume
    open_price, volume = client.calculate_volume(symbol, contract_value)

    # Place trade
    open_trade_id = client.buy(symbol, volume)

    # Store open data
    trade.open_price = open_price
    trade.volume = volume
    print(f"Opened trade with id: {open_trade_id}")

    open_trades = client.get_open_trades()
    for open_trade in open_trades:
        if open_trade['symbol'] == symbol:
            trade.position_id = open_trade['position'] - 1
            print("Transaction id: ", trade.position_id)


def close_trade(client: XTBTradingClient, trade: Trade, ):
    # Close trade
    client.sell(symbol, trade.volume)

    # Store close trade data
    profit = client.get_closed_trade_profit(trade.position_id)
    print("Profit today:", profit)
    trade.profit = profit


def find_profitable_instruments(client: XTBTradingClient, last_n_days: int, take_profit_percentage: float = 0.1,
                                total_successful_days_percentage: float = 0.49):
    """Go through all the symbols,

    Args:
        last_n_days (int): _description_
        take_profit_percentage (float, optional): _description_. Defaults to 0.1.
        total_successful_days_percentage (float, optional): _description_. Defaults to 0.49.
    """
    symbols = client.get_all_symbols()
    json_dict = read_json_from_file_named_with_today_date("profitable_symbols/")
    for symbol in symbols:
        try:
            history = client.get_last_n_candles_history(Instrument(symbol, interval), last_n_days)
            if history is None:
                continue
        except Exception as e:
            continue
        print(f"Investigating symbol: {symbol}")
        open_high = list(zip(history['open'], history['high']))
        total = 0
        for (open_price, high_price) in open_high:
            if high_price/open_price - 1.0 >= take_profit_percentage:
                total += 1
        if total/n > total_successful_days_percentage:
            if json_dict is None:
                json_dict = dict()
            if not json_dict.get(str(symbol)):
                json_dict[str(symbol)] = dict()
            json_dict[str(symbol)][str(last_n_days)] = {'take_profit_percentage': take_profit_percentage, 'total_successful_days': total}
            print("Success", symbol, total/n)
        else:
            print("Failure.")
    write_json_to_file_named_with_today_date(json_dict, "profitable_symbols/")


def calculate_average_tp(open_high_close, from_index, to_index):
    return sum([(high_price / open_price - 1) for open_price, high_price, close_price in open_high_close]) / (to_index - from_index + 1)


def calculate_average_tp_full(open_high_close):
    accumulated_p = sum([(high_price / open_price - 1) for open_price, high_price, close_price in open_high_close])
    return accumulated_p / len(open_high_close)


def round_to_print(decimal_number: float):
    return str(round(decimal_number, 2))


def calculate_potential_profits(client: XTBTradingClient, open_high_close, last_n_days: int,
                                take_profit_percentage: float = 0.1,
                                contract_value: int = 1000,
                                symbol: str = "EURUSD"):
    total = 0
    for (open_price, high_price, close_price) in open_high_close[last_n_days:2*last_n_days-1]:
        if high_price/open_price - 1.0 > take_profit_percentage:
            cp = open_price * (1.0 + take_profit_percentage)
        else:
            cp = close_price
        volume = int(contract_value/open_price)
        total += client.get_profit_calculation(symbol, open_price, cp, volume, 0)

    profit = round_to_print(total)
    contract_value = round_to_print(volume * open_price)
    print(f"Symbol: {symbol} Profit: {profit} Volume: {str(volume)}, Contract value: {contract_value}")


if __name__ == '__main__':
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, mode, False)

    n = 100
    p = 0.1
    interval = '1D'
    symbol = 'CRTO.US_9'


    # LAST_N_DAYS = 30
    # history = client.get_last_n_candles_history(Instrument(symbol, '1D'), 2 * LAST_N_DAYS)
    # open_high_close = list(zip(history['open'], history['high'], history['close']))
    # avg_tp = calculate_average_tp(open_high_close, 0, LAST_N_DAYS - 1)
    # print(f"AVG TP: {avg_tp}")
    # calculate_potential_profits(client, open_high_close, LAST_N_DAYS, avg_tp, 1000, symbol)


    history = client.get_last_n_candles_history(Instrument(symbol, '1D'), 100)
    open_high_close = list(zip(history['open'], history['high'], history['close']))
    avg_tp_100 = calculate_average_tp_full(open_high_close)

    history = client.get_last_n_candles_history(Instrument(symbol, '1D'), 10)
    open_high_close = list(zip(history['open'], history['high'], history['close']))
    avg_tp_10 = calculate_average_tp_full(open_high_close)
    weighted_tp = (avg_tp_100 + 2.0 * avg_tp_10) / 3.0

    avg_tp_100_str = round_to_print(avg_tp_100)
    avg_tp_10_str = round_to_print(avg_tp_10)
    weighted_tp_str = round_to_print(weighted_tp)
    print(f"AVG TP 100: {avg_tp_100_str} and AVG TP 10: {avg_tp_10_str} and WEIGHTED_TP: {weighted_tp_str}")


    date_now_cet = get_date_now_cet()

    if not client.is_market_open(symbol):
        print(f"Market is closed for {symbol}, go to sleep")
        is_market_open = False
        while not is_market_open:
            is_market_open = client.is_market_open(symbol)
            time.sleep(1)

    if weighted_tp < 0.05:
        print(f"Weighted tp {weighted_tp_str} < 0.05, will not trade today")

    else:
        enter_trade(client, 1000, symbol, weighted_tp)

    # find_profitable_instruments(client, 100, 0.05, 0.49)
