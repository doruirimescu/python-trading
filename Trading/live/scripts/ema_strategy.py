from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument.instrument import Instrument
from Trading.algo.indicators.indicator import bollinger_bands, moving_average, EMAIndicator
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis

from Trading.algo.strategy.strategy import EmaStrategy

from dotenv import load_dotenv
import os
import logging
import pandas as pd


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

    N_CANDLES = 2000
    history = client.get_last_n_candles_history(Instrument('GOLD', '4h'), N_CANDLES)


    print(type(history))
    main_data = pd.DataFrame(history)

    IS_LONG_TRADE_OPEN = False
    IS_SHORT_TRADE_OPEN = False
    trade_open_price = 0
    total_profit = 0
    for i in range(100, N_CANDLES):
        df = main_data.iloc[0: i]

        ema30 = EMAIndicator(30)
        em_30 = ema30.calculate_ema(df[:-1])

        ema50 = EMAIndicator(50)
        em_50 = ema50.calculate_ema(df[:-1])

        ema100 = EMAIndicator(100)
        em_100 = ema100.calculate_ema(df[:-1])
        trend = ema100.get_trend()

        current_price_high = df.iloc[-1]['high']
        current_price_low = df.iloc[-1]['low']

        TP = 1.01
        SPREAD = 0.3
        if trend == TrendAnalysis.UP:
            if IS_LONG_TRADE_OPEN is False and current_price_low <= em_30:
                IS_LONG_TRADE_OPEN = True
                trade_open_price = current_price_low
                print("ENTER LONG TRADE")

            if IS_LONG_TRADE_OPEN:
                potential_profit = current_price_high - trade_open_price - SPREAD
                print("Potential long profit", potential_profit)

                if (trade_open_price + potential_profit)/trade_open_price > TP:
                    #take profit
                    IS_LONG_TRADE_OPEN = False
                    total_profit += potential_profit
                    print("WIN LONG TRADE", potential_profit)
                    potential_profit = 0

                elif current_price_high <= em_100:
                    #stop loss
                    IS_LONG_TRADE_OPEN = False
                    total_profit += potential_profit
                    print("LOSE LONG TRADE", potential_profit)
                    potential_profit = 0

        if trend == TrendAnalysis.SIDE:
            if IS_LONG_TRADE_OPEN or IS_SHORT_TRADE_OPEN:
                print("CLOSE SIDE TRADE", potential_profit)
                total_profit += potential_profit
                potential_profit = 0
                IS_SHORT_TRADE_OPEN = False
                IS_LONG_TRADE_OPEN = False

        elif trend == TrendAnalysis.DOWN:
            if IS_SHORT_TRADE_OPEN is False and current_price_high >= em_30:
                #place trade
                IS_SHORT_TRADE_OPEN = True
                trade_open_price = current_price_high
                print("ENTER SHORT TRADE")

            if IS_SHORT_TRADE_OPEN:
                potential_profit = trade_open_price - current_price_low - SPREAD
                print("Potential short profit", potential_profit)

                if (trade_open_price + potential_profit)/trade_open_price > TP:
                    #take profit
                    IS_SHORT_TRADE_OPEN = False
                    total_profit += potential_profit
                    print("WIN SHORT TRADE", potential_profit)
                    potential_profit = 0

                elif current_price_high >= em_100:
                    #stop loss
                    IS_SHORT_TRADE_OPEN = False
                    total_profit += potential_profit
                    print("LOSE SHORT TRADE", potential_profit)
                    potential_profit = 0

    print("TOTAL PROFIT:", total_profit)
