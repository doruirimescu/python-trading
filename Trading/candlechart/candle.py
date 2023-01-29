from enum import Enum
import datetime
import calendar

from Trading.live.investing_api.investing_candlestick import PatternAnalysis

class CandleType(Enum):
    """According to https://en.wikipedia.org/wiki/Candlestick_pattern"""

    BIG = -1  # Distinguish with body
    BODY = 0  # Distinguish with big
    DOJI = 1
    LONG_LEGGED_DOJI = 2
    DRAGONFLY_DOJI = 3
    GRAVESTONE_DOJI = 4
    HAMMER = 5  # Distinguish with shaven head
    HANGINGMAN = 6  # Same as hammer, but in downtrend
    INVERTED_HAMMER = 7  # Distinguish with shaven bottom
    SHOOTING_STAR = 8  # Same as inverted hammer, but in uptrend
    MARUBOZU = 9
    SPINNING_TOP = 10
    SHAVEN_HEAD = 11  # Distinguish with hammer
    SHAVEN_BOTTOM = 12  # Distinguish with inverted_hammer
    UNDEFINED = 13


class CandleTypeWithConfidence:
    def __init__(self, type, confidence):
        self.type = type
        self.confidence = confidence


class Color(Enum):
    RED = 0
    BLACK = 0
    GREEN = 1
    WHITE = 1


# Wt, Wb, b
candle_type_dict = {
    CandleType.MARUBOZU: (0.0, 0.0, 1.0),
    CandleType.BODY: (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    CandleType.DOJI: (0.5, 0.5, 0.0),
    CandleType.DRAGONFLY_DOJI: (0.0, 1.0, 0.0),
    CandleType.GRAVESTONE_DOJI: (1.0, 0.0, 0.0),
    CandleType.HAMMER: (0, 2.0 / 3.0, 1.0 / 3.0),
    CandleType.INVERTED_HAMMER: (2.0 / 3.0, 0.0, 1.0 / 3.0),
}


class CandleClassifier:
    def __init__(self, candle, confidence_limit=50.0):
        self.open_ = candle.open_
        self.close_ = candle.close_
        self.high_ = candle.high_
        self.low_ = candle.low_

        self.swing_ = abs(self.high_ - self.low_)

        # Would cause divisions by zero
        if self.swing_ == 0.0:
            self.type_with_confidence_ = CandleType.UNDEFINED
            return

        self.body_ = abs(self.open_ - self.close_) / (abs(self.high_ - self.low_))

        self.c_ = candle.getColor() == Color.GREEN

        self.wt_ = (
            self.high_ - (self.c_ * self.close_ + (1 - self.c_) * self.open_)
        ) / self.swing_
        self.wb_ = (
            (self.c_ * self.open_ + (1 - self.c_) * self.close_) - self.low_
        ) / self.swing_

        self.confidence_limit_ = confidence_limit
        self.type_with_confidence_ = self.__classify()

    def getWickBottom(self):
        return self.wb_

    def getWickTop(self):
        return self.wt_

    def getType(self):
        return self.type_with_confidence_

    def __classify(self):
        """Calculate error from ideal type for each possible type, and return the one with maximum match in percentage

        Returns:
            [CandleType]: classified candle type
        """
        classifications = dict()
        for ideal_tuple in candle_type_dict:
            error = 0.0
            error += abs(self.wt_ - candle_type_dict[ideal_tuple][0])
            error += abs(self.wb_ - candle_type_dict[ideal_tuple][1])
            error += abs(self.body_ - candle_type_dict[ideal_tuple][2])
            error *= 100.0
            error = max(0, 100.0 - error)
            classifications[ideal_tuple] = error

        best_match = max(classifications, key=classifications.get)
        confidence = classifications[best_match]

        # TODO Clarify between Doji and Long-legged doji
        # TODO Clarify between Inverted Hammer and Shooting star

        # Clarify between hammer and shaven_head
        if best_match == CandleType.HAMMER:
            if self.wt_ < 0.05:
                best_match = CandleType.SHAVEN_HEAD

        # Clarify between inverted hammer and shaven_head
        if best_match == CandleType.INVERTED_HAMMER:
            if self.wb_ < 0.05:
                best_match = CandleType.SHAVEN_BOTTOM

        if confidence < self.confidence_limit_:
            best_match = CandleType.UNDEFINED

        return CandleTypeWithConfidence(best_match, round(confidence, 2))


class Candle:
    def __init__(self, open, high, low, close, date=None):
        self.validate(open, close, high, low)

        self.open_ = open
        self.close_ = close
        self.high_ = high
        self.low_ = low
        self.candlestick_analysis_ = PatternAnalysis()

        if self.open_ < self.close_:
            self.color_ = Color.GREEN
        else:
            self.color_ = Color.RED

        self.date_ = date

        classifier = CandleClassifier(self)
        self.type_with_confidence_ = classifier.getType()

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

    def getColor(self):
        return self.color_

    def getTypeWithConfidence(self):
        return self.type_with_confidence_

    def getWeekday(self):
        return calendar.day_name[self.date_.weekday()]

    def setTechnicalAnalysis(self, analysis):
        self.technical_analysis_ = analysis

    def getTechnicalAnalysis(self):
        return self.technical_analysis_

    def setPatternAnalysis(self, analysis):
        self.candlestick_analysis_ = analysis

    def getPatternAnalysis(self):
        return self.candlestick_analysis_

    def getData(self):
        return (
            self.open_,
            self.high_,
            self.low_,
            self.close_,
            self.date_,
            self.technical_analysis_,
            self.candlestick_analysis_,
        )

    def __repr__(self):
        return "(Open: {o} High: {h} Low: {l} Close: {c} Date: {d} Tech: {t} Pat: {p})".format(
            o=self.open_,
            h=self.high_,
            l=self.low_,
            c=self.close_,
            d=self.date_,
            t=self.technical_analysis_,
            p=self.candlestick_analysis_,
        )
