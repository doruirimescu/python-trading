import pytest
import unittest
from Trading.candlechart.candle import Candle
from Trading.candlechart.candle import CandleClassifier

class TestCandleClassifier(unittest.TestCase):

    def test_getWickBottom(self):
        cc = CandleClassifier(Candle(2.0,3.0,0.0,1.0))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.333, 3)

        cc = CandleClassifier(Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.25, 2)

        cc = CandleClassifier(Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.25, 2)

        cc = CandleClassifier(Candle(0.25,1.0,0.0,0.5))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.25, 2)

        cc = CandleClassifier(Candle(0.25,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.25, 2)

        cc = CandleClassifier(Candle(0.251,0.251,0.25,0.25))
        self.assertAlmostEqual(cc.get_wick_bottom(), 0.0, 2)

        cc = CandleClassifier(Candle(0.8,1.0,0.0,0.2))
        self.assertAlmostEqual(cc.get_wick_top(), 0.2, 2)

    def test_getWickTop(self):
        cc = CandleClassifier(Candle(2.0,3.0,0.0,1.0))
        self.assertAlmostEqual(cc.get_wick_top(), 0.333, 3)

        cc = CandleClassifier(Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_top(), 0.5, 2)

        cc = CandleClassifier(Candle(0.5,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_top(), 0.5, 2)

        cc = CandleClassifier(Candle(0.25,1.0,0.0,0.5))
        self.assertAlmostEqual(cc.get_wick_top(), 0.5, 2)

        cc = CandleClassifier(Candle(0.25,1.0,0.0,0.25))
        self.assertAlmostEqual(cc.get_wick_top(), 0.75, 2)

        cc = CandleClassifier(Candle(0.251,0.251,0.25,0.25))
        self.assertAlmostEqual(cc.get_wick_top(), 0.0, 2)

        cc = CandleClassifier(Candle(0.8,1.0,0.0,0.2))
        self.assertAlmostEqual(cc.get_wick_top(), 0.2, 2)

if __name__ == '__main__':
    unittest.main()
