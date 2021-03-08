
import pytest
import unittest
import datetime

from Trading.InvestingAPI.investing_technical import TechnicalAnalysis

from Trading.Candlechart.candle import Candle
from Trading.Candlechart.candle import Color
from Trading.Candlechart.candle import CandleType
class TestCandle(unittest.TestCase):

    def test_getColor(self):
        c = Candle(1.0, 2.0,0.0,4.0)
        self.assertEqual(c.getColor(), Color.GREEN)

        c = Candle(1.0, 2.0,0.0,0.6)
        self.assertEqual(c.getColor(), Color.RED)

    def test_getTypeWithConfidence_doji(self):
        doji = Candle(0.6,1,0,0.5)
        type_with_confidence = doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_doji_perfect(self):
        doji = Candle(0.49999,1,0,0.5)
        type_with_confidence = doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 100.0,2)

    def test_getTypeWithConfidence_dragonfly_doji(self):
        dragonfly_doji = Candle(0.9,1,0,1.0)
        type_with_confidence = dragonfly_doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.DRAGONFLY_DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_grave_doji(self):
        grave_doji = Candle(0.0,1,0,0.1)
        type_with_confidence = grave_doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.GRAVESTONE_DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_marubozu(self):
        marubozu = Candle(0.0,1,0,0.99)
        type_with_confidence = marubozu.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.MARUBOZU)
        self.assertAlmostEqual(type_with_confidence.confidence, 98.0,2)

    def test_getTypeWithConfidence_hammer(self):
        hammer = Candle(0.7,1,0,0.9)
        type_with_confidence = hammer.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.HAMMER)
        self.assertAlmostEqual(type_with_confidence.confidence, 73.33,2)

    def test_getTypeWithConfidence_shaven_head(self):
        shaven_head = Candle(0.8,1,0,0.99)
        type_with_confidence = shaven_head.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.SHAVEN_HEAD)
        self.assertAlmostEqual(type_with_confidence.confidence, 71.33,2)

    def test_getTypeWithConfidence_inverted_hammer(self):
        inverted_hammer = Candle(0.1,1,0,0.3)
        type_with_confidence = inverted_hammer.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.INVERTED_HAMMER)
        self.assertAlmostEqual(type_with_confidence.confidence, 73.33,2)

    def test_getTypeWithConfidence_shaven_bottom(self):
        shaven_bottom = Candle(0.0,1,0,0.3)
        type_with_confidence = shaven_bottom.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.SHAVEN_BOTTOM)
        self.assertAlmostEqual(type_with_confidence.confidence, 93.33,2)

    def test_getTypeWithConfidence_body(self):
        body = Candle(0.25,1,0,0.7)
        type_with_confidence = body.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, CandleType.BODY)
        self.assertAlmostEqual(type_with_confidence.confidence, 76.67,2)

    def test_getTechnicalAnalysis(self):
        body = Candle(0.25,1,0,0.7)

        body.setTechnicalAnalysis(TechnicalAnalysis.STRONG_SELL)
        self.assertEqual(body.getTechnicalAnalysis(), TechnicalAnalysis.STRONG_SELL)

        body.setTechnicalAnalysis(TechnicalAnalysis.SELL)
        self.assertEqual(body.getTechnicalAnalysis(), TechnicalAnalysis.SELL)

        body.setTechnicalAnalysis(TechnicalAnalysis.NEUTRAL)
        self.assertEqual(body.getTechnicalAnalysis(), TechnicalAnalysis.NEUTRAL)

        body.setTechnicalAnalysis(TechnicalAnalysis.BUY)
        self.assertEqual(body.getTechnicalAnalysis(), TechnicalAnalysis.BUY)

        body.setTechnicalAnalysis(TechnicalAnalysis.STRONG_BUY)
        self.assertEqual(body.getTechnicalAnalysis(), TechnicalAnalysis.STRONG_BUY)

    def test_getWeekday(self):
        body = Candle(0.25,1,0,0.7, datetime.date(2021,3,5))
        self.assertEqual(body.getWeekday(), 'Friday')

        body = Candle(0.25,1,0,0.7, datetime.date(2020,12,31))
        self.assertEqual(body.getWeekday(), 'Thursday')

        body = Candle(0.25,1,0,0.7, datetime.date(2030,5,15))
        self.assertEqual(body.getWeekday(), 'Wednesday')

if __name__ == '__main__':
    unittest.main()
