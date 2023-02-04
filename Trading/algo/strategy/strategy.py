from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from dataclasses import dataclass
import logging

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
