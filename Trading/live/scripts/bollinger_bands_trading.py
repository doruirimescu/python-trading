from Trading.live.client.client import XTBTradingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Timeframe, Instrument
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
from Trading.utils.argument_parser import CustomParser
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

    cp = CustomParser()

    cp.add_xtb_username()
    cp.add_xtb_password()
    cp.add_xtb_mode()
    cp.add_instrument()


    username, password, mode, symbol, timeframe = cp.parse_args()
    client = XTBTradingClient(username, password, mode, False)

    N_CANDLES = 2000
    history = client.get_last_n_candles_history(Instrument(symbol, Timeframe(timeframe)), N_CANDLES)


    TP = 0.05
    SPREAD = 0.3
    ema_buy_strategy = EmaBuyStrategy(TP)
    ema_sell_strategy = EmaSellStrategy(TP)

    bb_buy_strategy = BollingerBandsStrategy(StrategyType.BUY)
    bb_sell_strategy = BollingerBandsStrategy(StrategyType.SELL)

    bb_buy_strategy.spread, bb_sell_strategy.spread = SPREAD, SPREAD
    bb_buy_strategy.logger = MAIN_LOGGER
    bb_sell_strategy.logger = MAIN_LOGGER

    BUY_TRADE_ID = None
    SELL_TRADE_ID = None

    def print_statement():
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

    while True:
        if client.is_market_open('GOLD'):
            history = client.get_last_n_candles_history(Instrument('GOLD', Timeframe('5m')), 200)
            main_data = pd.DataFrame(history)
            bid, ask = client.get_current_price('GOLD')

            if not bb_buy_strategy.is_trade_open:
                a = bb_buy_strategy.analyse(main_data, ask)
                if a == Action.BUY:
                    BUY_TRADE_ID = client.buy('GOLD', 0.01)['order']
            else:
                a = bb_buy_strategy.analyse(main_data, bid)
                if a == Action.STOP:
                    client.close_trade(BUY_TRADE_ID)
                    print_statement()

            if not bb_sell_strategy.is_trade_open:
                a = bb_sell_strategy.analyse(main_data, bid)
                if a == Action.SELL:
                    SELL_TRADE_ID = client.sell('GOLD', 0.01)['order']
            else:
                a = bb_sell_strategy.analyse(main_data, ask)
                if a == Action.STOP:
                    client.close_trade(SELL_TRADE_ID)
                    print_statement()
        sleep(0.1)
