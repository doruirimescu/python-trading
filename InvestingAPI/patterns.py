from enum import Enum


class CandlestickPatternIndication(Enum):
    BEARISH_REVERSAL = "Bearish reversal",
    BULLISH_REVERSAL = "Bullish reversal",
    BULLISH_CONTINUATION = "Bullish continuation",
    BEARISH_CONTINUATION = "Bearish continuation"

class CandlestickPatternReliability(Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'

class CandlestickPattern:
    def __init__(self, name, indication, reliability, description=""):
        self.name = name
        self.indication = indication
        self.description = description
        self.reliability = reliability

    def __repr__(self):
        r = "Pattern name: {name}\nIndication: {indication} \nReliability: {reliability} \nDescription: {description}".format(
            name=self.name, indication=self.indication, reliability=self.reliability.name, description=self.description
        )
        return r

class EngulfingBearish(CandlestickPattern):
    def __init__(self):
        name = "Engulfing Bearish"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.MEDIUM
        description = """
    Occurring during an uptrend, this pattern characterized by a large black real body, which engulfs a white real body (it doesn't need to engulf the shadows).
    This signifies that the uptrend has been hurt and the bears may be gaining strength. The Engulfing indicator is also the first two candles of the Three Outside patterns.
    It is a major reversal signal. Factors that are increasing this signal's reliability:

    1) The first candlestick has a very small real body and the second candlestick a very large real body.

    2) The pattern appears after a protracted or very fast move.

    3) Heavy volume on the second black candlestick.

    4) The second candlestick engulfs more than one real body."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class BullishEngulfing(CandlestickPattern):
    def __init__(self):
        name = "Bullish Engulfing"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.MEDIUM
        description = """
    During a downtrend, the Bullish Engulfing depicts an opening at a new low and closes at or above the previous candle's open.
    This signifies that the downtrend has lost momentum and the bulls may be gaining strength. Factors increasing the pattern's effectiveness are:

    1) The first candlestick has a small real body and the second has a large real body.

    2) Pattern appears after protracted or very fast move.

    3) Heavy volume on second real body.

    4) The second candlestick engulfs more than one real body."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class ThreeInsideUp(CandlestickPattern):
    def __init__(self):
        name = "Three Inside Up"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
    This pattern is a more reliable addition to the standard Harami pattern.
    A bullish Harami pattern occurs in the first two candles.
    The third candle is a white candle with a higher close than the second candle and the confirmation of the bullish trend reversal."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class ThreeInsideDown(CandlestickPattern):
    def __init__(self):
        name = "Three Inside Down"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
    This pattern is a more reliable addition to the standard Harami pattern.
    A bearish Harami pattern occurs in the first two candles.
    The third candle is a black one with a lower close than the second.
    The third candlestick is confirmation of the bearish trend reversal."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class BeltHoldBearish(CandlestickPattern):
    def __init__(self):
        name = "Belt Hold Bearish"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.LOW
        description = """
    During an uptrend, a black body occurs in an upside gap with an open that is also the high for the candle.
    This may cause many positions to be sold, perpetuating a bearish reversal.
    The longer the height of the belt-hold candlestick the more significant the pattern is."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class BeltHoldBullish(CandlestickPattern):
    def __init__(self):
        name = "Belt Hold Bullish"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.LOW
        description = """
    During a downtrend, a white body occurs with an open that is also the low for it. This may signify a start of rally for the bulls.
    The larger the white candlestick is, the more significant it is."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class DarkCloudCover(CandlestickPattern):
    def __init__(self):
        name = "Dark Cloud Cover"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
    During an uptrend, the first candlestick is a long white one.
    The second candlestick is black with an open above the high of the previous candlestick and close within but below the midpoint of the first candlestick's body.
    The Dark Cloud Cover pattern suggests an opportunity for the shorts to capitalize on the next candlestick's open.
    It is a warning sign for bullish investors.
    The greater the penetration of the first candlestick by the second and the higher the volume is on the second candle, the more significant this pattern is.
    In addition, if the second body opens above a major resistance level - it may indicate a strong reversal.
    The Dark Cloud Cover pattern is the opposite of the Piercing line pattern."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class PiercingLine(CandlestickPattern):
    def __init__(self):
        name = "Piercing Line"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """..."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class MorningDojiStar(CandlestickPattern):
    def __init__(self):
        name = "Morning Doji Star"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
    During a downtrend, the market strengthens the bearish trend with a long black candlestick.
    The second candlestick trades within a small range and closes at or near its open.
    This scenario generally shows the potential for a rally, as many positions have been changed.
    Confirmation of the trend reversal is given by the white third candlestick.
    The Morning Doji Star is a fully realized bullish Doji Star pattern.
    It is important reversal signal."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class EveningDojiStar(CandlestickPattern):
    def __init__(self):
        name = "Evening Doji Star"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
    During an uptrend, the market builds strength on a long white candlestick.
    The second candlestick trades within a small range and closes at or near its open.
    This scenario generally shows an erosion of confidence in the current trend.
    Confirmation of the trend reversal is the black third candlestick.
    The Evening Doji Star indicator is the fully realized bearish Doji Star pattern."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class InvertedHammer(CandlestickPattern):
    def __init__(self):
        name = "Inverted Hammer"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.LOW
        description = """
    During a downtrend, the open is lower, then it trades higher, but closes near its open, therefore looking like an inverted lollipop.
    It needs bullish verification on the next candlestick."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class ShootingStar(CandlestickPattern):
    def __init__(self):
        name = "Shooting Star"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.LOW
        description = """
    During an uptrend, a gap up occurs. It rallies to a new high then loses strength and closes near its low: a bearish change of momentum.
    Confirmation of the trend reversal would by an opening below the body of the Shooting Star on the next trading candle. It is not a major reversal signal as the evening star.
    Ideally, real body would gap away from previous body."""
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class ThreeBlackCrows(CandlestickPattern):
    def __init__(self):
        name = "Three Black Crows"
        indication = CandlestickPatternIndication.BEARISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
        During an uptrend, three long black candles occur with consecutively lower closes.
        This pattern suggests that the market has been at a high price for too long, and investors are beginning to compensate for it.
        More significant if it appears after a mature advance.
        """
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class ThreeWhiteSoldiers(CandlestickPattern):
    def __init__(self):
        name = "Three White Soldiers"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
        During a downtrend, three long white candlesticks occur with consecutively higher closes.
        Generally this suggests future market fortitude, as a reversal is in progress and is building on moderate upward steps.
        """
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class AbandonedBabyBullish(CandlestickPattern):
    def __init__(self):
        name = "Abandoned Baby Bullish"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """
        A very rare pattern characterized by a downside "Doji" gap which is then followed by an upside gap.
        The shadows on the "Doji" must completely gap below the shadows of the first and third candlesticks.
        """
        CandlestickPattern.__init__(self, name, indication, reliability, description)

class AbandonedBabyBearish(CandlestickPattern):
    def __init__(self):
        name = "Abandoned Baby Bearish"
        indication = CandlestickPatternIndication.BULLISH_REVERSAL
        reliability = CandlestickPatternReliability.HIGH
        description = """...
        """
        CandlestickPattern.__init__(self, name, indication, reliability, description)

# class FallingThreeMethods(CandlestickPattern)

# class RisingThreeMethods(CandlestickPattern)
p = AbandonedBabyBearish()
print(p)
