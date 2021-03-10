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
        self.__overbought = overbought
        self.__oversold = oversold
        self.__neutral = neutral
        self.__neutral_low = 50 - neutral
        self.__neutral_high = 50 + neutral

    def analyse(self, value):
        if value > self.__overbought:
            return IndicatorAction.OVERBOUGHT
        elif value < self.__oversold:
            return IndicatorAction.OVERSOLD
        elif (value >= self.__neutral_low) and (value <= self.__neutral_high):
            return IndicatorAction.NEUTRAL
        elif value > self.__neutral_high and value <= self.__overbought:
            return IndicatorAction.BUY
        elif value < self.__neutral_low and value >= self.__oversold:
            return IndicatorAction.SELL
