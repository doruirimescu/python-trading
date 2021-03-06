import candle
import pytest
import unittest
import datetime
from bs4 import BeautifulSoup as bs
from investing import InvestingAnalysisResponse

class TestCandle(unittest.TestCase):

    def test_getColor(self):
        c = candle.Candle(1.0, 2.0,0.0,4.0)
        self.assertEqual(c.getColor(), candle.Color.GREEN)

        c = candle.Candle(1.0, 2.0,0.0,0.6)
        self.assertEqual(c.getColor(), candle.Color.RED)

    def test_getTypeWithConfidence_doji(self):
        doji = candle.Candle(0.6,1,0,0.5)
        type_with_confidence = doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_doji_perfect(self):
        doji = candle.Candle(0.49999,1,0,0.5)
        type_with_confidence = doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 100.0,2)

    def test_getTypeWithConfidence_dragonfly_doji(self):
        dragonfly_doji = candle.Candle(0.9,1,0,1.0)
        type_with_confidence = dragonfly_doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.DRAGONFLY_DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_grave_doji(self):
        grave_doji = candle.Candle(0.0,1,0,0.1)
        type_with_confidence = grave_doji.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.GRAVESTONE_DOJI)
        self.assertAlmostEqual(type_with_confidence.confidence, 80.0,2)

    def test_getTypeWithConfidence_marubozu(self):
        marubozu = candle.Candle(0.0,1,0,0.99)
        type_with_confidence = marubozu.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.MARUBOZU)
        self.assertAlmostEqual(type_with_confidence.confidence, 98.0,2)

    def test_getTypeWithConfidence_hammer(self):
        hammer = candle.Candle(0.7,1,0,0.9)
        type_with_confidence = hammer.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.HAMMER)
        self.assertAlmostEqual(type_with_confidence.confidence, 73.33,2)

    def test_getTypeWithConfidence_shaven_head(self):
        shaven_head = candle.Candle(0.8,1,0,0.99)
        type_with_confidence = shaven_head.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.SHAVEN_HEAD)
        self.assertAlmostEqual(type_with_confidence.confidence, 71.33,2)

    def test_getTypeWithConfidence_inverted_hammer(self):
        inverted_hammer = candle.Candle(0.1,1,0,0.3)
        type_with_confidence = inverted_hammer.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.INVERTED_HAMMER)
        self.assertAlmostEqual(type_with_confidence.confidence, 73.33,2)

    def test_getTypeWithConfidence_shaven_bottom(self):
        shaven_bottom = candle.Candle(0.0,1,0,0.3)
        type_with_confidence = shaven_bottom.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.SHAVEN_BOTTOM)
        self.assertAlmostEqual(type_with_confidence.confidence, 93.33,2)

    def test_getTypeWithConfidence_body(self):
        body = candle.Candle(0.25,1,0,0.7)
        type_with_confidence = body.getTypeWithConfidence()
        self.assertEqual(type_with_confidence.type, candle.CandleType.BODY)
        self.assertAlmostEqual(type_with_confidence.confidence, 76.67,2)

    def test_getInvestingAnalysis(self):
        body = candle.Candle(0.25,1,0,0.7)

        body.setInvestingAnalysis(InvestingAnalysisResponse.STRONG_SELL)
        self.assertEqual(body.getInvestingAnalysis(), InvestingAnalysisResponse.STRONG_SELL)

        body.setInvestingAnalysis(InvestingAnalysisResponse.SELL)
        self.assertEqual(body.getInvestingAnalysis(), InvestingAnalysisResponse.SELL)

        body.setInvestingAnalysis(InvestingAnalysisResponse.NEUTRAL)
        self.assertEqual(body.getInvestingAnalysis(), InvestingAnalysisResponse.NEUTRAL)

        body.setInvestingAnalysis(InvestingAnalysisResponse.BUY)
        self.assertEqual(body.getInvestingAnalysis(), InvestingAnalysisResponse.BUY)

        body.setInvestingAnalysis(InvestingAnalysisResponse.STRONG_BUY)
        self.assertEqual(body.getInvestingAnalysis(), InvestingAnalysisResponse.STRONG_BUY)

    def test_getWeekday(self):
        body = candle.Candle(0.25,1,0,0.7, datetime.date(2021,3,5))
        self.assertEqual(body.getWeekday(), 'Friday')

        body = candle.Candle(0.25,1,0,0.7, datetime.date(2020,12,31))
        self.assertEqual(body.getWeekday(), 'Thursday')

        body = candle.Candle(0.25,1,0,0.7, datetime.date(2030,5,15))
        self.assertEqual(body.getWeekday(), 'Wednesday')

if __name__ == '__main__':
    unittest.main()
