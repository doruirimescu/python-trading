from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from dataclasses import dataclass
import logging
from Trading.algo.indicators.indicator import EMAIndicator, BollingerBandsIndicator, BollingerBandsResult
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
import pandas as pd
from typing import Optional, List
from abc import abstractmethod
from enum import Enum

__all__ = ["Action", "decide_action"]

class Action(Enum):
    BUY = "buy",    # to enter a trade with buy
    SELL = "sell",   # to enter a trade with sell
    NO = "no",     # no action
    STOP = "stop"    # to close a trade


class StrategyType(Enum):
    BUY = "buy",
    SELL = "sell"


def decide_action(previous_analysis: TechnicalAnalysis, current_analysis: TechnicalAnalysis):
    """Given a previous and current analysis, decide what action to take.

    Args:
        previous_analysis (TechnicalAnalysis): Previous analysis for given instrument.
        current_analysis (TechnicalAnalysis): Current analysis for given instrument.

    Returns:
        Action: Action to take.
    """
    LOGGER = logging.getLogger('strategy')
    # Create abbreviations for ease of use
    SS = TechnicalAnalysis.STRONG_SELL
    S = TechnicalAnalysis.SELL
    N = TechnicalAnalysis.NEUTRAL
    B = TechnicalAnalysis.BUY
    SB = TechnicalAnalysis.STRONG_BUY

    NO = Action.NO
    STOP = Action.STOP
    BUY = Action.BUY
    SELL = Action.SELL
    decisions = {
        (SS, SS):   NO,
        (SS, S):    NO,
        (SS, N):    STOP,
        (SS, B):    STOP,
        (SS, SB):   STOP,
        (S, SS):    NO,
        (S, S):     NO,
        (S, N):     STOP,
        (S, B):     STOP,
        (S, SB):    STOP,
        (N, SS):    SELL,
        (N, S):     NO,
        (N, N):     NO,
        (N, B):     NO,
        (N, SB):    BUY,
        (B, SS):    STOP,
        (B, S):     STOP,
        (B, N):     STOP,
        (B, B):     NO,
        (B, SB):    NO,
        (SB, SS):   STOP,
        (SB, S):    STOP,
        (SB, N):    STOP,
        (SB, B):    NO,
        (SB, SB):   NO}
    LOGGER.debug("Deciding action for previous analysis: %s, current analysis: %s", previous_analysis, current_analysis)
    if previous_analysis is None or current_analysis is None:
        return NO
    return decisions[(previous_analysis, current_analysis)]



class DailyBuyStrategy:
    """Buy and wait for take profit, then close. Once per day.
    """
    #TODO: take last_100_days_take_profit_percentage, last_10_days_take_profit_percentage
    #TODO:  last_10_days_take_profit_percentage < 0.05, do not trade.
    #TODO: weighted mean between last_100 and last_10 with weight on 2:1
    def __init__(self, take_profit_percentage: float):
        # Should take the last 100 days candles of the instrument and check if to sell or buy
        self._take_profit_percentage = take_profit_percentage

    def analyse(self, has_already_traded_instrument_today: bool = False, open_price: float = 0.0,
                current_price: float = 0.0, is_market_closing_soon: bool = False) -> TechnicalAnalysis:
        """Buy once per day (when market opens). Wait for take profit target to be achieved and close trade. If target not achieved, close when market is closing.

        Args:
            has_already_traded_instrument_today (bool): True if instrument has already been traded once today
            open_price (float): Price at which market opened today for this instrument
            current_price (float): Current price of this instrument
            is_market_closing_soon (bool): If market is closing soon (soon is to be defined by caller)

        Returns:
            TechnicalAnalysis: STRONG_BUY if to open trade, STRONG_SELL if to close trade, NEUTRAL if to not do anything
        """
        if not has_already_traded_instrument_today:
            return Action.BUY
        else:
            if 1 - current_price/open_price >= self._take_profit_percentage:
                return Action.SELL
            if is_market_closing_soon:
                return Action.SELL
        return Action.NO


class Strategy:
    def __init__(self, strategy_type: StrategyType) -> None:
        self.returns: List[float] = list()
        self.trade_open_price: Optional[float] = None
        self.is_trade_open: bool = False
        self.strategy_type = strategy_type

    def _place_trade(self) -> Action:
        if self.strategy_type == StrategyType.BUY:
            return Action.BUY
        else:
            return Action.SELL

    @abstractmethod
    def _is_take_profit_condition(self, potential_profit: float) -> bool:
        pass

    @abstractmethod
    def _is_stop_loss_condition(self, current_price: float, ema_slow_value: float) -> bool:
        pass

    def _calculate_potential_profit(self, current_price: float) -> float:
        if not self.trade_open_price:
            return 0.0

        if self.strategy_type == StrategyType.SELL:
            return self.trade_open_price - current_price
        else:
            return current_price - self.trade_open_price

    def _accumulate_profit(self, current_price: float) -> None:
        new_profit = self._calculate_potential_profit(current_price)
        self.returns.append(new_profit)

    def get_type(self) -> str:
        return self.strategy_type.value

    def get_total_profit(self) -> float:
        return sum(self.returns)

    def log_enter(self, current_price: float) -> None:
        print(f"Entering {self.get_type()} trade at {current_price} price")

    def log_exit(self, current_price: float) -> None:
        print(f"Exiting {self.get_type()} trade at {current_price} price")


class EmaStrategy(Strategy):
    def __init__(self,
                 strategy_type: StrategyType,
                 take_profit_percentage: float,
                 ema_fast_indicator: EMAIndicator = EMAIndicator(30),
                 ema_mid_indicator: EMAIndicator = EMAIndicator(50),
                 ema_slow_indicator: EMAIndicator = EMAIndicator(100)) -> None:
        super().__init__(strategy_type)
        self.take_profit_percentage = take_profit_percentage
        self.ema_fast_indicator = ema_fast_indicator
        self.ema_mid_indicator = ema_mid_indicator
        self.ema_slow_indicator = ema_slow_indicator

    def analyse(self,
                df: pd.DataFrame,
                current_price: float) -> TechnicalAnalysis:

        ema_fast_value = self.ema_fast_indicator.calculate_ema(df)
        ema_mid_value  = self.ema_mid_indicator.calculate_ema(df)
        ema_slow_value = self.ema_slow_indicator.calculate_ema(df)
        trend = self.ema_slow_indicator.get_trend(30)

        if self._is_trend_condition(trend):
            if not self.is_trade_open and self._is_price_within_channel(current_price, ema_fast_value, ema_mid_value):
                self.is_trade_open = True
                self.trade_open_price = current_price
                self.log_enter(current_price)
                return self._place_trade()

            elif self.is_trade_open:
                potential_profit = self._calculate_potential_profit(current_price)

                if self._is_take_profit_condition(potential_profit):
                    # Take profit
                    self._accumulate_profit(current_price)
                    self.log_exit(current_price)
                    self.is_trade_open = False
                    self.trade_open_price = None
                    return Action.STOP

                elif self._is_stop_loss_condition(current_price, ema_slow_value):
                    # Stop loss
                    self._accumulate_profit(current_price)
                    self.log_exit(current_price)
                    self.is_trade_open = False
                    self.trade_open_price = None
                    return Action.STOP

        elif self.is_trade_open:
            self._accumulate_profit(current_price)
            self.log_exit(current_price)
            self.is_trade_open = False
            self.trade_open_price = None
            return Action.STOP

        return Action.NO

    def _is_take_profit_condition(self, potential_profit: float) -> bool:
        if self.trade_open_price:
            return potential_profit / self.trade_open_price > self.take_profit_percentage
        else:
            return False

    def _is_trend_condition(self, trend: TrendAnalysis) -> bool:
        if self.strategy_type == StrategyType.BUY:
            return trend == TrendAnalysis.UP
        else:
            return trend == TrendAnalysis.DOWN

    def _is_stop_loss_condition(self, current_price: float, ema_slow_value: float) -> bool:
        if self.strategy_type == StrategyType.BUY:
            return current_price <= ema_slow_value
        else:
            return current_price >= ema_slow_value

    def _is_price_within_channel(self,
                                 current_price: float,
                                 ema_fast_value: float,
                                 ema_mid_value: float) -> bool:
        if self.strategy_type == StrategyType.BUY:
            return current_price <= ema_fast_value and current_price >= ema_mid_value
        else:
            return current_price >= ema_fast_value and current_price <= ema_mid_value


class EmaBuyStrategy(EmaStrategy):
    def __init__(self, take_profit_percentage: float,
                 ema_fast_indicator: EMAIndicator = EMAIndicator(30),
                 ema_mid_indicator: EMAIndicator = EMAIndicator(50),
                 ema_slow_indicator: EMAIndicator = EMAIndicator(100)) -> None:
        super().__init__(StrategyType.BUY, take_profit_percentage, ema_fast_indicator, ema_mid_indicator, ema_slow_indicator)



class EmaSellStrategy(EmaStrategy):
    def __init__(self, take_profit_percentage: float,
                 ema_fast_indicator: EMAIndicator = EMAIndicator(30),
                 ema_mid_indicator: EMAIndicator = EMAIndicator(50),
                 ema_slow_indicator: EMAIndicator = EMAIndicator(100)) -> None:
        super().__init__(StrategyType.SELL, take_profit_percentage, ema_fast_indicator, ema_mid_indicator, ema_slow_indicator)


class BollingerBandsStrategy(Strategy):
    def __init__(self,
                 strategy_type: StrategyType,
                 bb_indicator: BollingerBandsIndicator = BollingerBandsIndicator(window=20, num_std=2)) -> None:
        super().__init__(strategy_type)
        self.bb_indicator = bb_indicator

    def analyse(self,
                df: pd.DataFrame,
                current_price: float) -> TechnicalAnalysis:
        indicator_result = self.bb_indicator.calculate_bb(df)

        #! Add trend condition
        if self._is_trade_condition(indicator_result, current_price):
            if not self.is_trade_open:
                self.is_trade_open = True
                self.trade_open_price = current_price
                self.log_enter(current_price)
                return self._place_trade()
            elif self.is_trade_open and self._is_close_condition(indicator_result, current_price):
                self._accumulate_profit(current_price)

    @abstractmethod
    def _is_trade_condition(self, indicator_result: BollingerBandsResult, current_price: float) -> bool:
        if self.strategy_type == StrategyType.BUY:
            return current_price <= indicator_result.low_band
        else:
            return current_price >= indicator_result.high_band

    @abstractmethod
    def _is_close_condition(self, indicator_result: BollingerBandsResult, current_price: float) -> bool:
        if self.strategy_type == StrategyType.BUY:
            return current_price >= indicator_result.mean
        else:
            return current_price <= indicator_result.mean
