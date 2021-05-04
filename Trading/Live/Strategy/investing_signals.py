
#! Monitor investing.com
# Neutral -> Strong Buy  buy
# Neutral -> Strong Sell sell
#
#
#
from Trading.Algo.TechnicalAnalyzer.technical_analysis import TechnicalAnalysis
from enum import Enum
__all__ = ["Action", "TransactionType", "decideAction", "decideTransaction"]


class Action:
    BUY = "buy",    # to enter a trade with buy
    SELL = "sell",   # to enter a trade with sell
    NO = "no",     # no action
    STOP = "stop"    # to close a trade


class TransactionType:
    BUY = "buy",
    SELL = "sell"
    NO = "no"


def decideAction(previous_analysis: TechnicalAnalysis, current_analysis: TechnicalAnalysis):
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
    return decisions[(previous_analysis, current_analysis)]


def decideTransaction(action_to_take: Action, current_position: TransactionType):

    if current_position == TransactionType.BUY:
        if action_to_take == Action.SELL:
            return Action.STOP

    if current_position == TransactionType.SELL:
        pass
