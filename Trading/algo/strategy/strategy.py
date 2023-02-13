from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from dataclasses import dataclass
import logging
from Trading.algo.indicators.indicator import EMAIndicator
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
import pandas as pd
from typing import Optional
from abc import abstractmethod

__all__ = ["Action", "decide_action"]

@dataclass
class Action:
    BUY = "buy",    # to enter a trade with buy
    SELL = "sell",   # to enter a trade with sell
    NO = "no",     # no action
    STOP = "stop"    # to close a trade


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



class EmaStrategy:
    def __init__(self,
                 take_profit_percentage: float,
                 ema_fast_indicator: EMAIndicator = EMAIndicator(30),
                 ema_mid_indicator: EMAIndicator = EMAIndicator(50),
                 ema_slow_indicator: EMAIndicator = EMAIndicator(100)) -> None:
        self.take_profit_percentage: float = take_profit_percentage
        self.is_trade_open: bool = False
        self.trade_open_price: Optional[float] = None
        self.ema_fast_indicator = ema_fast_indicator
        self.ema_mid_indicator = ema_mid_indicator
        self.ema_slow_indicator = ema_slow_indicator
        self.total_profit = 0.0

    def analyse(self,
                df: pd.DataFrame,
                current_price: float) -> TechnicalAnalysis:

        ema_fast_value = self.ema_fast_indicator.calculate_ema(df)
        ema_mid_value = self.ema_mid_indicator.calculate_ema(df)
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

    @abstractmethod
    def _place_trade(self):
        pass

    @abstractmethod
    def _is_trend_condition(self, trend: TrendAnalysis) -> bool:
        pass

    @abstractmethod
    def _is_take_profit_condition(self, potential_profit: float) -> bool:
        pass

    @abstractmethod
    def _is_stop_loss_condition(self, current_price: float, ema_slow_value: float) -> bool:
        pass

    @abstractmethod
    def _is_price_within_channel(self,
                                 current_price: float,
                                 ema_fast_value: float,
                                 ema_mid_value: float) -> bool:
        pass

    @abstractmethod
    def _calculate_potential_profit(self, current_price: float) -> float:
        pass

    @abstractmethod
    def _accumulate_profit(self, current_price: float) -> None:
        pass

    @abstractmethod
    def get_total_profit(self) -> float:
        pass

    @abstractmethod
    def get_type(self) -> str:
        pass

    @abstractmethod
    def log_enter(self, current_price: float) -> None:
        pass

    @abstractmethod
    def log_exit(self, current_price: float) -> None:
        pass


class EmaBuyStrategy(EmaStrategy):
    def _place_trade(self):
        return Action.BUY

    def _is_trend_condition(self, trend: TrendAnalysis) -> bool:
        return trend == TrendAnalysis.UP

    def _is_take_profit_condition(self, potential_profit: float) -> bool:
        if self.trade_open_price:
            return potential_profit / self.trade_open_price > self.take_profit_percentage
        else:
            return False

    def _is_stop_loss_condition(self, current_price: float, ema_slow_value: float) -> bool:
        return current_price <= ema_slow_value

    def _is_price_within_channel(self,
                                 current_price: float,
                                 ema_fast_value: float,
                                 ema_mid_value: float) -> bool:
        return current_price <= ema_fast_value and current_price >= ema_mid_value

    def _calculate_potential_profit(self, current_price: float) -> float:
        if self.trade_open_price:
            return current_price - self.trade_open_price
        else:
            return 0.0

    def _accumulate_profit(self, current_price: float) -> None:
        self.total_profit += self._calculate_potential_profit(current_price)

    def get_total_profit(self) -> float:
        return self.total_profit

    def get_type(self) -> str:
        return "BUY"

    def log_enter(self, current_price: float) -> None:
        print(f"Entering {self.get_type()} trade at {current_price} price")

    def log_exit(self, current_price: float) -> None:
        print(f"Exiting {self.get_type()} trade at {current_price} price")


class EmaSellStrategy(EmaBuyStrategy):
    def _place_trade(self):
        return Action.SELL

    def _is_trend_condition(self, trend: TrendAnalysis) -> bool:
        return trend == TrendAnalysis.DOWN

    def _is_take_profit_condition(self, potential_profit: float) -> bool:
        if self.trade_open_price:
            return potential_profit / self.trade_open_price > self.take_profit_percentage
        else:
            return False

    def _is_stop_loss_condition(self, current_price: float, ema_slow_value: float) -> bool:
        return current_price >= ema_slow_value

    def _is_price_within_channel(self,
                                 current_price: float,
                                 ema_fast_value: float,
                                 ema_mid_value: float) -> bool:
        return current_price >= ema_fast_value and current_price <= ema_mid_value

    def _calculate_potential_profit(self, current_price: float) -> float:
        if self.trade_open_price:
            return self.trade_open_price - current_price
        else:
            return 0.0

    def get_type(self) -> str:
        return "SELL"
