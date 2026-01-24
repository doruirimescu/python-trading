import unittest

from mrscore.components.mean.ema import EMA


class TestEMA(unittest.TestCase):
    def test_min_periods_warmup_running_mean(self) -> None:
        ema = EMA(span=3, min_periods=2)
        self.assertFalse(ema.is_ready())

        self.assertAlmostEqual(ema.update(2.0), 2.0)
        self.assertFalse(ema.is_ready())

        self.assertAlmostEqual(ema.update(4.0), 3.0)
        self.assertTrue(ema.is_ready())

        # alpha = 2 / (span + 1) = 0.5
        self.assertAlmostEqual(ema.update(6.0), 4.5)

    def test_min_periods_one_uses_ema_after_first(self) -> None:
        ema = EMA(span=4, min_periods=1)
        self.assertAlmostEqual(ema.update(10.0), 10.0)
        self.assertTrue(ema.is_ready())

        alpha = 2.0 / (4 + 1.0)
        expected = alpha * 15.0 + (1.0 - alpha) * 10.0
        self.assertAlmostEqual(ema.update(15.0), expected)

    def test_reset_clears_state(self) -> None:
        ema = EMA(span=2, min_periods=2)
        ema.update(5.0)
        ema.update(7.0)
        self.assertTrue(ema.is_ready())

        ema.reset()
        self.assertFalse(ema.is_ready())
        self.assertAlmostEqual(ema.value, 0.0)

        self.assertAlmostEqual(ema.update(3.0), 3.0)
