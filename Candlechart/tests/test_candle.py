import candle
import pytest
import unittest

class TestCandle(unittest.TestCase):

    def test_getColor(self):
        c = candle.Candle(1.0, 2.0,0.0,4.0)
        self.assertEqual(c.getColor(), candle.Color.GREEN)

        c = candle.Candle(1.0, 2.0,0.0,0.6)
        self.assertEqual(c.getColor(), candle.Color.RED)

    def test_getBodyPercentage(self):
        c = candle.Candle(1.0, 3.0, 0.0, 4.0)
        result = c.getBodyPercentage()
        self.assertAlmostEqual(result, 1.0, 3)

        c = candle.Candle(1.0, 4.0, 0.0, 0.0)
        result = c.getBodyPercentage()
        self.assertAlmostEqual(result, 0.25, 3)


if __name__ == '__main__':
    unittest.main()
