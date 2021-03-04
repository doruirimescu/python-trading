import candle
import pytest
import unittest

class TestCandle(unittest.TestCase):

    def test_isGreen(self):
        c = candle.Candle(1.0,2.0,3.0,4.0)
        self.assertTrue(c.isGreen())

        c = candle.Candle(2.0, 1.0, 3.0, 4.0)
        self.assertFalse(c.isGreen())

    def test_getBodyPercentage(self):
        TOL = 1e-3
        c = candle.Candle(1.0,2.0,3.0,4.0)
        result = c.getBodyPercentage()
        self.assertAlmostEqual(result, 1.0, TOL)

        c = candle.Candle(1.0,2.0,0.0,4.0)
        result = c.getBodyPercentage()
        self.assertAlmostEqual(result, 0.25, TOL)

        c = candle.Candle(0.1,0.2,0.1,0.2)
        result = c.getBodyPercentage()
        self.assertAlmostEqual(result, 1.0, TOL)


if __name__ == '__main__':
    unittest.main()
