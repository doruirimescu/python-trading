from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument, Timeframe
from Trading.algo.indicators.indicator import EMAIndicator, BollingerBandsIndicator
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis, TechnicalAnalysis
from Trading.algo.strategy.strategy import Action, StrategyType, BollingerBandsStrategy
import matplotlib.pyplot as plt
from Trading.algo.strategy.strategy import EmaBuyStrategy, EmaSellStrategy
from time import sleep
from Trading.utils.calculations import (calculate_sharpe_ratio,
                                        calculate_percentage_losers,
                                        calculate_max_consecutive_losers,
                                        calculate_max_drawdown)

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

    N_CANDLES = 1000
    history = client.get_last_n_candles_history(Instrument('SILVER', Timeframe('15m')), N_CANDLES)

    # history = read_historical_data("data/historical/gold-15m.json")
    main_data = pd.DataFrame(history)


    TP = 0.05
    SPREAD = 0.3
    ema_buy_strategy = EmaBuyStrategy(TP)
    ema_sell_strategy = EmaSellStrategy(TP)

    bb_buy_strategy = BollingerBandsStrategy(StrategyType.BUY)
    bb_sell_strategy = BollingerBandsStrategy(StrategyType.SELL)
    bb_buy_strategy.spread, bb_sell_strategy.spread = SPREAD, SPREAD

    ema_slow_indicator: EMAIndicator = EMAIndicator(100)
    ema_slow_indicator.calculate_ema(main_data, 'close')

    bb_indicator: BollingerBandsIndicator = BollingerBandsIndicator(window=20, num_std=2)
    fig, ax = plt.subplots(figsize=(10, 5))
    bb_indicator.calculate_bb(main_data)
    # bb_indicator.plot(ax)
    ax.plot(main_data['high'], label=f'high price', color='green')
    ax.plot(main_data['low'], label=f'low price', color='red')
    ema_slow_indicator.plot(ax)
    plt.show()


    BUY_TRADE_ID = None
    SELL_TRADE_ID = None


    for i in range(100, len(main_data)):
        df = main_data.iloc[0: i]
        current_price_high = df.iloc[-1]['open']
        current_price_low = df.iloc[-1]['low']

        # ema_buy_strategy.analyse(df, current_price_low)
        # ema_sell_strategy.analyse(df, current_price_high)

        if not bb_buy_strategy.is_trade_open and not bb_sell_strategy.is_trade_open:
            a = bb_buy_strategy.analyse(df, current_price_low)
            if a == Action.BUY:
                print("BOUGhT AT InDEX ", i)
        else:
            bb_buy_strategy.analyse(df, current_price_high)

        if not bb_buy_strategy.is_trade_open and not bb_sell_strategy.is_trade_open:
            a = bb_sell_strategy.analyse(df, current_price_high)
            if a == Action.SELL:
                print("SOLD AT InDEX ", i)
        else:
            bb_sell_strategy.analyse(df, current_price_low)


    buy_profit = round(bb_buy_strategy.get_total_profit(), 2)
    sell_profit = round(bb_sell_strategy.get_total_profit(), 2)
    total_profit = round(buy_profit + sell_profit, 2)
    min_return = min(bb_buy_strategy.get_min_return(), bb_sell_strategy.get_min_return())
    min_return = round(min_return, 2)
    all_returns = bb_buy_strategy.returns + bb_sell_strategy.returns
    sharpe_ratio = calculate_sharpe_ratio(all_returns)
    sharpe_ratio = round(sharpe_ratio * 252**0.5, 2)
    MAIN_LOGGER.info(f"Buy p: {buy_profit} sell p: {sell_profit} total p: {total_profit} min return: {min_return}")
    MAIN_LOGGER.info(f"Percent losers: {calculate_percentage_losers(all_returns)}")
    MAIN_LOGGER.info(f"Maximum consecutive losers: {calculate_max_consecutive_losers(all_returns)}")
    MAIN_LOGGER.info(f"Maximum drawdown: {calculate_max_drawdown(all_returns)}")
