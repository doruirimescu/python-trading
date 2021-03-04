import candle
import pytest
import unittest

class TestCandleClassifier(unittest.TestCase):

    def test_getWickBottom(self):
        cc = candle.CandleClassifier(candle.Candle(2.0,3.0,0.0,1.0))
        self.assertAlmostEqual(cc.getWickBottom(), 0.333, 3)

        cc = candle.CandleClassifier(candle.Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickBottom(), 0.25, 2)

        cc = candle.CandleClassifier(candle.Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickBottom(), 0.25, 2)

        cc = candle.CandleClassifier(candle.Candle(0.25,1.0,0.0,0.5))
        self.assertAlmostEqual(cc.getWickBottom(), 0.25, 2)

        cc = candle.CandleClassifier(candle.Candle(0.25,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickBottom(), 0.25, 2)

        cc = candle.CandleClassifier(candle.Candle(0.251,0.251,0.25,0.25))
        self.assertAlmostEqual(cc.getWickBottom(), 0.0, 2)

        cc = candle.CandleClassifier(candle.Candle(0.8,1.0,0.0,0.2))
        self.assertAlmostEqual(cc.getWickTop(), 0.2, 2)

    def test_getWickTop(self):
        cc = candle.CandleClassifier(candle.Candle(2.0,3.0,0.0,1.0))
        self.assertAlmostEqual(cc.getWickTop(), 0.333, 3)

        cc = candle.CandleClassifier(candle.Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickTop(), 0.5, 2)

        cc = candle.CandleClassifier(candle.Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickTop(), 0.5, 2)

        cc = candle.CandleClassifier(candle.Candle(0.25,1.0,0.0,0.5))
        self.assertAlmostEqual(cc.getWickTop(), 0.5, 2)

        cc = candle.CandleClassifier(candle.Candle(0.25,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.getWickTop(), 0.75, 2)

        cc = candle.CandleClassifier(candle.Candle(0.251,0.251,0.25,0.25))
        self.assertAlmostEqual(cc.getWickTop(), 0.0, 2)

        cc = candle.CandleClassifier(candle.Candle(0.8,1.0,0.0,0.2))
        self.assertAlmostEqual(cc.getWickTop(), 0.2, 2)

if __name__ == '__main__':
    unittest.main()
