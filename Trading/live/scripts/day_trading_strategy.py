from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import (get_date_now_cet,
                                get_datetime_now_cet,
                                get_seconds_to_next_date)
from Trading.algo.strategy.strategy import DailyBuyStrategy, Action
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.trade.trade import TradeType, Trade
from Trading.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.utils.write_to_file import (write_json_to_file_named_with_today_date,
                                        read_json_from_file_named_with_today_date,
                                        read_json_file)
from Trading.utils.argument_parser import CustomParser

from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import round_to_two_decimals, calculate_mean_take_profit, calculate_weighted_mean_take_profit
from typing import List, Tuple, Callable
import logging
import time
import sys


def enter_trade(client: XTBTradingClient, contract_value: int,
                symbol: str, take_profit_percentage: float) -> Trade:
    date_now_cet = get_date_now_cet()
    todays_trade = Trade(date_=date_now_cet, type_=TradeType.BUY, contract_value=contract_value)
    daily_buy_strategy = DailyBuyStrategy(take_profit_percentage)

    if daily_buy_strategy.analyse(has_already_traded_instrument_today=False) == Action.BUY:
        order2_id = open_trade(client, todays_trade, contract_value)

    # Prepare to close trade
    IS_TRADE_CLOSED = False
    while not IS_TRADE_CLOSED:
        current_price = client.get_current_price(symbol)[0]
        is_market_closing_soon = client.is_market_closing_in_n_seconds(symbol, 90)
        should_close_trade = daily_buy_strategy.analyse(
                                True, todays_trade.open_price,
                                current_price, is_market_closing_soon) == Action.SELL

        if  should_close_trade:
            close_trade(client, todays_trade, order2_id)
            todays_trade.close_price = current_price
            IS_TRADE_CLOSED = True
        time.sleep(1)
    return todays_trade


def open_trade(client: XTBTradingClient, trade: Trade, contract_value: int) -> int:
    # Calculate volume
    open_price, volume = client.calculate_volume_bid(symbol, contract_value)

    if volume <= 0:
        raise Exception("Contract value is too small")

    # Place trade
    open_trade_id = client.buy(symbol, volume)['order']

    # Store open data
    trade.open_price = open_price
    trade.volume = volume
    print(f"Opened trade with order 2 id: {open_trade_id}")

    open_trades = client.get_open_trades()

    for open_trade in open_trades:
        if open_trade['symbol'] == symbol and open_trade['order2'] == open_trade_id:
            trade.position_id = open_trade['position'] - 1
            print("Transaction id: ", trade.position_id)
            print("Order2 ", open_trade['order2'])
            print("Order ", open_trade['order'])
    return int(open_trade_id)


def close_trade(client: XTBTradingClient, trade: Trade, open_trade_id: int):
    print(f"Closing {trade.position_id} at time {str(get_datetime_now_cet())}")
    try:
        # Only works for stocks
        client.sell(symbol, trade.volume)
        time.sleep(5)
    except Exception as e:
        print("Could not close/sell")
        print(e)

    # Store close trade data. Only works for stocks
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
            history = client.get_last_n_candles_history(Instrument(symbol, Timeframe(interval)), last_n_days)
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
        if total/last_n_days > total_successful_days_percentage:
            if json_dict is None:
                json_dict = dict()
            if not json_dict.get(str(symbol)):
                json_dict[str(symbol)] = dict()
            json_dict[str(symbol)][str(last_n_days)] = {'take_profit_percentage': take_profit_percentage, 'total_successful_days': total}
            print("Success", symbol, total/last_n_days)
        else:
            print("Failure.")
    write_json_to_file_named_with_today_date(json_dict, "profitable_symbols/")


def calculate_potential_profits(get_profit_calculation: Callable[[str, float, float, float, int], float],
                                open_high_close: List[Tuple[float, float, float]],
                                take_profit_percentage: float = 0.1,
                                cash_amount: int = 1000,
                                symbol: str = "EURUSD",
                                n_days: int = 100):
    total = 0
    for (open_price, high_price, close_price) in open_high_close:
        if high_price/open_price - 1.0 > take_profit_percentage:
            cp = open_price * (1.0 + take_profit_percentage)
        else:
            cp = close_price
        volume = int(cash_amount/open_price)
        total += get_profit_calculation(symbol, open_price, cp, volume, 0)

    profit = round_to_two_decimals(total)
    contract_value = round_to_two_decimals(volume * open_price)
    print(f"Symbol: {symbol} Profit: {profit} Volume: {str(volume)}, Contract value: {contract_value}")

    json_dict = read_json_from_file_named_with_today_date("profit_calculations/")
    if json_dict is None:
        json_dict = dict()
    json_dict[symbol] = {'profit': profit, 'volume': volume,
                         'contract_value': contract_value, 'take_profit': take_profit_percentage,
                         'n_days': n_days}
    write_json_to_file_named_with_today_date(json_dict, "profit_calculations/")


def sleep_until_market_opens(client: XTBTradingClient, LOGGER: logging.Logger) -> None:
    is_market_open = client.is_market_open(symbol)
    if not is_market_open:
        LOGGER.info(f"Market is closed for {symbol} will have to sleep")

    while not is_market_open:
        is_market_open = client.is_market_open(symbol)
        time.sleep(1)
    LOGGER.info(f"Woke up from sleep")

IS_SAFE_TRADING = True

if __name__ == '__main__':
    start_time = get_datetime_now_cet()
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    if IS_SAFE_TRADING and MODE == "real":
        print("Trading with a live client. Do you wish to continue ? y/n")
        should_continue = input().strip()
        if should_continue.lower() != "y":
            sys.exit(0)

    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    cp = CustomParser()
    cp.add_instrument()
    cp.add_contract_value()

    symbol, interval, contract_value = cp.parse_args()
    history = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), 100)
    open_high_100 = list(zip(history['open'], history['high']))
    weighted_tp = calculate_weighted_mean_take_profit(open_high_100, 10, 2, MAIN_LOGGER)

    open_price, volume = client.calculate_volume_bid(symbol, contract_value)
    MAIN_LOGGER.info(f"VOLUME: {volume}")
    from_t, to_t = client.get_trading_hours_today_cet(symbol)
    time_now = get_datetime_now_cet()

    sleep_until_market_opens(client, MAIN_LOGGER)

    if IS_SAFE_TRADING and weighted_tp < 0.05:
        MAIN_LOGGER.info(f"Weighted tp {weighted_tp} < 0.05, will not trade today")
    else:
        todays_trade = enter_trade(client, contract_value, symbol, weighted_tp)
        as_dict = todays_trade.get_dict()
        write_json_to_file_named_with_today_date(as_dict, "trades/")



    #! Profitable symbols
    # profitable_symbols = read_json_file("profitable_symbols/2023-01-29").keys()
    # print(profitable_symbols)
    # N_DAYS = 100
    # for symbol in profitable_symbols:
    #     history = client.get_last_n_candles_history(Instrument(symbol, Timeframe('1D')), N_DAYS)
    #     ohc = list(zip(history['open'], history['high'], history['close']))
    #     calculate_potential_profits(client.get_profit_calculation, ohc, 0.1, contract_value, symbol, N_DAYS)

    #! Profitable instruments
    # find_profitable_instruments(client, 100, 0.05, 0.49)

#TODO: how to close stock, forex, etf ?
