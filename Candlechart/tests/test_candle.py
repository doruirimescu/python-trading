import candle
import pytest
import unittest

class TestCandle(unittest.TestCase):

    def test_getColor(self):
        c = candle.Candle(1.0, 2.0,0.0,4.0)
        self.assertEqual(c.getColor(), candle.Color.GREEN)

        c = candle.Candle(1.0, 2.0,0.0,0.6)
        self.assertEqual(c.getColor(), candle.Color.RED)

    def test_getType_doji(self):
        doji = candle.Candle(0.6,1,0,0.5)
        self.assertEqual(doji.getType(), candle.CandleType.DOJI)

    def test_getType_dragonfly_doji(self):
        dragonfly_doji = candle.Candle(0.9,1,0,1.0)
        self.assertEqual(dragonfly_doji.getType(), candle.CandleType.DRAGONFLY_DOJI)

    def test_getType_grave_doji(self):
        grave_doji = candle.Candle(0.0,1,0,0.1)
        self.assertEqual(grave_doji.getType(), candle.CandleType.GRAVESTONE_DOJI)

    def test_getType_marubozu(self):
        marubozu = candle.Candle(0.0,1,0,0.99)
        self.assertEqual(marubozu.getType(), candle.CandleType.MARUBOZU)

    def test_getType_hammer(self):
        hammer = candle.Candle(0.7,1,0,0.9)
        self.assertEqual(hammer.getType(), candle.CandleType.HAMMER)

    def test_getType_shaven_head(self):
        shaven_head = candle.Candle(0.8,1,0,0.99)
        self.assertEqual(shaven_head.getType(), candle.CandleType.SHAVEN_HEAD)

    def test_getType_inverted_hammer(self):
        inverted_hammer = candle.Candle(0.1,1,0,0.3)
        self.assertEqual(inverted_hammer.getType(), candle.CandleType.INVERTED_HAMMER)

    def test_getType_shaven_bottom(self):
        shaven_bottom = candle.Candle(0.0,1,0,0.3)
        self.assertEqual(shaven_bottom.getType(), candle.CandleType.SHAVEN_BOTTOM)

    def test_getType_body(self):
        body = candle.Candle(0.25,1,0,0.7)
        self.assertEqual(body.getType(), candle.CandleType.BODY)

if __name__ == '__main__':
    unittest.main()
