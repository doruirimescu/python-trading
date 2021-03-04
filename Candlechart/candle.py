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
    UNDEFINED = 12

class Color(Enum):
    RED = 0
    BLACK = 0
    GREEN = 1
    WHITE = 1

class CandleClassifier:
    def __init__(self, candle):
        self.open_  = candle.open_
        self.close_ = candle.close_
        self.high_  = candle.high_
        self.low_   = candle.low_

        self.swing_ = abs(self.high_-self.low_)
        self.body_ = abs(self.open_-self.close_)/(abs(self.high_-self.low_))


        self.c_ = candle.getColor() == Color.GREEN

        self.wt_ = (self.high_ -(self.c_*self.close_ + (1-self.c_)*self.open_)) / self.swing_
        self.wb_ = ((self.c_*self.open_ + (1-self.c_)*self.close_) - self.low_) / self.swing_

    def getWickBottom(self):
        return self.wb_

    def getWickTop(self):
        return self.wt_

class Candle:
    def __init__(self, open, high, low, close):
        """[summary]

        Args:
            open ([type]): [description]
            high ([type]): [description]
            low ([type]): [description]
            close ([type]): [description]
        """

        self.validate(open, close, high, low)

        self.open_ = open
        self.close_ = close
        self.high_ = high
        self.low_ = low

        if self.open_ < self.close_:
            self.color_ = Color.GREEN
        else:
            self.color_ = Color.RED

        self.body_percentage_ = float( abs(open-close)/(abs(high-low)) )
        self.type_ = self.__calcType()


    def validate(self, open, close, high, low):
        if open < 0.0:
            raise Exception("Open price smaller than 0")
        elif close < 0.0:
            raise Exception("Close price smaller than 0")
        elif high < 0.0:
            raise Exception("High price smaller than 0")
        elif low < 0.0:
            raise Exception("Low price smaller than 0")
        elif low > high:
            raise Exception("Low is higher than high")

    def getBodyPercentage(self):
        return self.body_percentage_

    def getColor(self):
        return self.color_

    def __calcType(self):
        if self.__isBig():
            return CandleType.BIG
        elif self.__isBody():
            return CandleType.BODY
        elif self.__isDoji():
            return CandleType.DOJI
        elif self.__isDragonFlyDoji():
            return CandleType.DRAGONFLY_DOJI
        elif self.__isGravestoneDoji():
            return CandleType.GRAVESTONE_DOJI
        elif self.__isHammer():
            return CandleType.HAMMER
        elif self.__isHangingMan():
            return CandleType.HANGINGMAN
        elif self.__isInvertedHammer():
            return CandleType.INVERTED_HAMMER
        elif self.__isLongLeggedDoji():
            return CandleType.LONG_LEGGED_DOJI
        elif self.__isMarubozu():
            return CandleType.MARUBOZU
        elif self.__isShavenBottom():
            return CandleType.SHAVEN_BOTTOM
        elif self.__isShavenHead():
            return CandleType.SHAVEN_HEAD
        elif self.__isShootingStar():
            return CandleType.SHOOTING_STAR
        elif self.__isSpinningTop():
            return CandleType.SPINNING_TOP
        else:
            return CandleType.UNDEFINED

    def getType(self):
        return self.type_

    def __isBig(self):
        return self.body_percentage_ >= 0.9

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


# c1 = Candle(1,2,3,1)

# print(c1.isGreen())
# print(c1.getType())
# print(c1.getBodyPercentage())
