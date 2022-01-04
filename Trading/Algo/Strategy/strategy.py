from Trading.Algo.TechnicalAnalyzer.technical_analysis import TechnicalAnalysis
from dataclasses import dataclass

__all__ = ["Action", "TransactionType", "decideAction"]

@dataclass
class Action:
    BUY  = "buy",    # to enter a trade with buy
    SELL = "sell",   # to enter a trade with sell
    NO   = "no",     # no action
    STOP = "stop"    # to close a trade

@dataclass
class TransactionType:
    BUY  = "buy",
    SELL = "sell"
    NO   = "no"

def decideAction(previous_analysis: TechnicalAnalysis, current_analysis: TechnicalAnalysis):
    """Given a previous and current analysis, decide what action to take.

    Args:
        previous_analysis (TechnicalAnalysis): Previous analysis for given instrument.
        current_analysis (TechnicalAnalysis): Current analysis for given instrument.

    Returns:
        Action: Action to take.
    """
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
