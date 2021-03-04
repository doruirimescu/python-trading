from enum import Enum
class CandleType(Enum):
    """According to https://en.wikipedia.org/wiki/Candlestick_pattern
    """
    BIG = -1
    BODY = 0
    DOJI = 1
    LONG_LEGGED_DOJI = 2
    DRAGONFLY_DOJI = 3
    GRAVESTONE_DOJI = 4
    HAMMER = 5
    HANGINGMAN = 6
    INVERTED_HAMMER = 7
    SHOOTING_STAR = 8
    MARUBOZU = 8
    SPINNING_TOP = 9
    SHAVEN_HEAD = 10
    SHAVEN_BOTTOM = 11

class Candle:
    def __init__(self, open, close, high, low):
        self.open_ = open
        self.close_ = close
        self.high_ = high
        self.low_ = low

        self.body_percentage_ = abs(open-close)/(abs(high-low))

    def getBodyPercentage(self):
        return self.body_percentage_

    def isGreen(self):
        if self.open_ < self.close_:
            return True
        else:
            return False

    def getType(self):
        return CandleType.BIG

    def __isBig(self):
        pass

    def __isBody(self):
        pass

    def __isDoji(self):
        pass

    def __isLongLeggedDoji(self):
        pass

    def __isDragonFlyDoji(self):
        pass

    def __isGravestoneDoji(self):
        pass

    def __isHammer(self):
        pass

    def __isHangingMan(self):
        pass

    def __isInvertedHammer(self):
        pass

    def __isShootingStar(self):
        pass

    def __isMarubozu(self):
        pass

    def __isSpinningTop(self):
        pass

    def __isShavenHead(self):
        pass

    def __isShavenBottom(self):
        pass


c1 = Candle(1,2,0,4)

print(c1.isGreen())
print(c1.getType())
print(c1.getBodyPercentage())
