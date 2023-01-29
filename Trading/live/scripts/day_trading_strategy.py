from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import get_date_now_cet
from exception_with_retry import ExceptionWithRetry, exception_with_retry
from Trading.utils.send_email import send_email_if_exception_occurs

from dotenv import load_dotenv
import os
import logging
import pandas as pd
import numpy as np
import time

import sys


def calculate_trade_profit(trade_open_price: float, trade_closing_price: float, position: str) -> float:
    if position.upper() == "SHORT":
        return trade_open_price - trade_closing_price
    elif position.upper() == "LONG":
        return trade_closing_price - trade_open_price
    else:
        raise ValueError("Invalid position provided. Position can only be 'SHORT' or 'LONG'.")

SYMBOLS = [
# 'CINE.UK_9',
# 'PBYI.US_9',
# 'CEVA.US_9',
# '3NGS.UK',
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

from dataclasses import dataclass
from datetime import date
@dataclass
class Trade:
    date_: date
    open_price: float
    close_price: float
    profit: float
    volume: int
    position_id: str

trades_dict = dict()


def performTrade(client, volume_eur: int, symbol: str, take_profit_percentage: float):
    global trades_dict

    date_now_cet = get_date_now_cet()
    if date_now_cet in trades_dict:
        print(f"Already traded today {date_now_cet}, go to sleep")
        return

    if not client.is_market_open(symbol):
        print(f"Market is closed for {symbol}, go to sleep")
        return

    todays_trade = Trade(date_now_cet, None, None, None, None, None)
    trades_dict[date_now_cet] = todays_trade

    # Calculate volume
    open_price = client.get_current_price(symbol)[1]
    volume = int(volume_eur/open_price)

    print(f"Calculate volume {volume} for symbol {symbol}")

    # Place trade
    open_trade_id = client.buy(symbol, volume)

    # Store open data
    todays_trade.open_price = open_price
    todays_trade.volume = volume
    print(f"Opened trade with id: {open_trade_id}")

    open_trades = client.get_open_trades()
    for trade in open_trades:
        if trade['symbol'] == symbol:
            todays_trade.transaction_id = trade['position'] - 1
            print("Transaction id: ", todays_trade.transaction_id)

    # Prepare to close trade
    IS_TRADE_CLOSED = False
    while not IS_TRADE_CLOSED:
        close_price = client.get_current_price(symbol)[0]
        potential_profit_percentage = 1.0 - close_price/open_price
        should_take_profit = potential_profit_percentage > take_profit_percentage
        is_market_closing_soon = client.is_market_closing_in_n_seconds(symbol, 90)

        if  should_take_profit or is_market_closing_soon:
            client.sell(symbol, volume)
            IS_TRADE_CLOSED = True
            todays_trade.close_price = close_price
            profit = client.get_closed_trade_profit(todays_trade.transaction_id)
            print("Profit today:", profit)
            todays_trade.profit = profit
        time.sleep(1)

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

    while True:
        performTrade(client, 100, symbol, 0.1)
        time.sleep(1)

    # for symbol in SYMBOLS:
    #     try:
    #         history = client.get_last_n_candles_history(instrument(symbol, interval), n)
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



    # symbols = client.get_all_symbols()
    # # Should remove _4
    # symbols = list(filter(lambda t: t[-2:] != "_4", symbols))
    # print(symbols)
    # for symbol in symbols:
    #     try:
    #         history = client.get_last_n_candles_history(instrument(symbol, interval), n)
    #     except Exception as e:
    #         continue

    #     open_high = list(zip(history['open_price'], history['high_price']))
    #     total = 0
    #     for (open_price, high_price) in open_high:
    #         if high_price/open_price - 1.0 > p:
    #             total += 1
    #     if total/n > 0.49:
    #         print("Success", symbol, total/n)


#TODO: dump jsons of last 1000 days for all instruments
