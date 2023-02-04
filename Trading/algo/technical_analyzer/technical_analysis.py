from enum import Enum


class TechnicalAnalysis(Enum):
    """Enumeration class for a technical analysis response"""

    STRONG_SELL = "Strong Sell"
    SELL        = "Sell"
    NEUTRAL     = "Neutral"
    BUY         = "Buy"
    STRONG_BUY  = "Strong Buy"

class TrendAnalysis(Enum):
    """Enumeration class for a trend analysis"""
    UP = "Upwards trend"
    DOWN = "Downwards trend"
    SIDE = "Sideways trend"
