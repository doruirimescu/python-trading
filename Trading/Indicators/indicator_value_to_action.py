from enum import Enum
class IndicatorAction(Enum):
    OVERBOUGHT  = "Overbought"
    OVERSOLD    = "Oversold"
    BUY         = "Buy"
    SELL        = "Sell"
    NEUTRAL     = "Neutral"

#An indicator value is between 0 and 100.
class IndicatorValueToAction:
    def __init__(self, overbought, oversold, neutral):
        self._overbought = overbought
        self._oversold = oversold
        self._neutral = neutral
        self._neutral_low = 50 - neutral
        self._neutral_high = 50 + neutral

    def analyse(self, value):
        if value > self._overbought:
            return IndicatorAction.OVERBOUGHT
        elif value < self._oversold:
            return IndicatorAction.OVERSOLD
        elif (value >= self._neutral_low) and (value <= self._neutral_high):
            return IndicatorAction.NEUTRAL
        elif value > self._neutral_high and value <= self._overbought:
            return IndicatorAction.BUY
        elif value < self._neutral_low and value >= self._oversold:
            return IndicatorAction.SELL
