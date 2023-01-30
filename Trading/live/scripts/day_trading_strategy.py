from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import get_date_now_cet
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
import pandas as pd
import numpy as np
import time
import json


SYMBOLS = [
'CINE.UK_9',
'PBYI.US_9',
'CEVA.US_9',
'3NGS.UK',
'SHLD.US_9',
'ENTA.US_9',
'TLS.US',
'ALTR.US_9',
'ICUI.US',
'TCMD.US_9',
'NVEI.US',
'CSTL.US_9',
'HLNE.US_9',
'XAN.US',
'VAL.US_9',
'CDLX.US_9',
'DSEY.US',
'CAMP.US_9',
'FOSL.US_9',
'TRST.US',
'CPS.US_9',
'ACRS.US',
'SRRK.US_9',
'ARCT.US',
'IGMS.US',
'APPF.US',
'TECH.US_9',
'VOR.US',
'INTU.UK_9',
'LIVN.US_9',
'PSNL.US_9',
'STOK.US',
'GLSI.US',
'SPT.US',
'EXAI.US',
'CRTO.US_9',
'GDEN.US',
'SGRY.US',
'GANX.US',
'LASR.US_9',
'RGNX.US_9',
'WVE.US']


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
    for trade in open_trades:
        if trade['symbol'] == symbol:
            trade.transaction_id = trade['position'] - 1
            print("Transaction id: ", trade.transaction_id)


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
    json_dict = read_json_from_file_named_with_today_date()
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
    write_json_to_file_named_with_today_date(json_dict)


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

    trades_dict: Dict[date, Trade] = dict()

    # while True:
    #     should_trade = True
    #     date_now_cet = get_date_now_cet()
    #     if date_now_cet in trades_dict:
    #         print(f"Already traded today {date_now_cet}, go to sleep")
    #         should_trade = False
    #     if not client.is_market_open(symbol):
    #         print(f"Market is closed for {symbol}, go to sleep")
    #         should_trade = False

    #     if should_trade:
    #         enter_trade(client, 100, symbol, 0.1)

    #     time.sleep(1)

    find_profitable_instruments(client, 100, 0.05, 0.49)

    # for symbol in SYMBOLS:
    #     try:
    #         history = client.get_last_n_candles_history(Instrument(symbol, interval), n)
    #     except Exception as e:
    #         continue
    #     open_high_close = list(zip(history['open'], history['high'], history['close']))
    #     total = 0
    #     for (open_price, high_price, close_price) in open_high_close:
    #         if high_price/open_price - 1.0 > p:
    #             cp = open_price * (1.0 + p)
    #         else:
    #             cp = close_price
    #         volume = int(1000/open_price)
    #         total += client.get_profit_calculation(symbol, open_price, cp, volume, 0)
    #         print(symbol, str(round(total, 2)), str(volume), str(round(volume * open_price, 2)))
    #     message = f"Symbol {symbol}, profit after 100 days at approx 1000 eur volumes : {str(total)}\n"

    #     f = open("backtest_results.txt", "a")
    #     f.write(message)
    #     f.close()
    #     print("Symbol " + symbol, "Profit after 100 days at {volume} units: " + str(total))



#TODO: dump jsons of last 1000 days for all instruments
