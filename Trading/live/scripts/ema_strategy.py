from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument.instrument import Instrument
from Trading.algo.indicators.indicator import bollinger_bands, moving_average, EMAIndicator
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
from Trading.algo.strategy.strategy import Action

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

    TP = 0.01
    SPREAD = 0.3
    ema_strategy = EmaStrategy(TP)

    IS_LONG_TRADE_OPEN = False
    IS_SHORT_TRADE_OPEN = False
    trade_open_price = 0
    total_profit = 0
    for i in range(100, N_CANDLES):
        df = main_data.iloc[0: i]
        current_price_high = df.iloc[-1]['high']
        current_price_low = df.iloc[-1]['low']
        current_price_open = df.iloc[-1]['open']

        if (not IS_LONG_TRADE_OPEN) and (not IS_SHORT_TRADE_OPEN):
            analysis = ema_strategy.analyse(df, current_price_low)
            if analysis == Action.BUY:
                print("Enter long trade", current_price_low)
                IS_LONG_TRADE_OPEN = True
                trade_open_price = current_price_low
            else:
                analysis = ema_strategy.analyse(df, current_price_high)
                if analysis == Action.SELL:
                    print("Enter short trade", current_price_high)
                    IS_SHORT_TRADE_OPEN = True
                    trade_open_price = current_price_high

        if IS_LONG_TRADE_OPEN:
            analysis = ema_strategy.analyse(df, current_price_high, False, True, trade_open_price)
            if analysis == Action.SELL:
                print("Close long trade", current_price_high)
                total_profit += (current_price_high - trade_open_price) - SPREAD
                IS_LONG_TRADE_OPEN = False
        if IS_SHORT_TRADE_OPEN:
            print("Close short trade", current_price_low)
            analysis = ema_strategy.analyse(df, current_price_low, True, False, trade_open_price)
            total_profit += (trade_open_price - current_price_low) - SPREAD
            IS_SHORT_TRADE_OPEN = False

    print("TOTAL PROFIT:", total_profit)
