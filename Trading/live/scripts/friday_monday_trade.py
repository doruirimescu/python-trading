from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument, Timeframe
from dotenv import load_dotenv
from Trading.utils.calculations import calculate_net_profit_eur
from Trading.live.hedge.fixed_conversion_rates import convert_currency_to_eur

import time
import os
import logging
import sys

def exit():
    sys.exit(0)

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
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    SYMBOL = 'CHFHUF'
    N_CANDLES = 100
    BUY_SELL = 1
    VOLUME = 0.15
    history = client.get_last_n_candles_history(Instrument(SYMBOL, Timeframe('1D')), N_CANDLES)
    info = client.get_symbol(SYMBOL)
    contract_value = VOLUME * info['contractSize']
    conversion_rate_eur = convert_currency_to_eur(info['currencyProfit'])
    swap_short = info['swapShort']
    print(contract_value)
    print(info)
    swap = swap_short * contract_value / 100
    spread_raw = info['spreadRaw'] * contract_value
    spread_raw = 10
    print(f"Swap: {swap} at contract value {contract_value} spread {spread_raw}")

    sell_price = None
    total_profit = 0
    min_drawdown = 1000
    profit = 0

    for date, open, close, low in zip(history['date'], history['open'], history['close'], history['low']):

        weekday = date.weekday()
        # print(f"Weekday: {weekday}")
        if weekday == 4:
            # Friday
            sell_price = close
            print(f"Sell on Friday at: {sell_price}")
        elif weekday == 0 and sell_price != None:
            # Monday
            close_price = open
            print(f"Close on Monday at: {close_price}")
            new_profit = calculate_net_profit_eur(sell_price, close_price, contract_value, conversion_rate_eur, BUY_SELL) + swap * 3 - spread_raw
            total_profit += new_profit
            if new_profit < min_drawdown:
                min_drawdown = new_profit
            if new_profit < 0 and profit < 0:
                print(f"----------TWO LOSSES In A ROW {new_profit} {profit}----------")
            profit = new_profit
            sell_price = None
    print(f"Total profit: {round(total_profit, 2)} with drawdown: {round(min_drawdown, 2)}")
