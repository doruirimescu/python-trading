import unittest

from mrscore.components.mean.rolling_sma import RollingSMA


class TestRollingSMA(unittest.TestCase):
    def test_window_one_tracks_last_value(self) -> None:
        sma = RollingSMA(window=1)
        self.assertFalse(sma.is_ready())

        self.assertAlmostEqual(sma.update(10.0), 10.0)
        self.assertTrue(sma.is_ready())

        self.assertAlmostEqual(sma.update(12.5), 12.5)
        self.assertAlmostEqual(sma.value, 12.5)

    def test_warmup_uses_available_samples(self) -> None:
        sma = RollingSMA(window=3)

        self.assertAlmostEqual(sma.update(1.0), 1.0)
        self.assertFalse(sma.is_ready())

        self.assertAlmostEqual(sma.update(3.0), 2.0)
        self.assertFalse(sma.is_ready())

        self.assertAlmostEqual(sma.update(5.0), 3.0)
        self.assertTrue(sma.is_ready())

    def test_rolls_over_window(self) -> None:
        sma = RollingSMA(window=3)

        sma.update(1.0)
        sma.update(2.0)
        sma.update(3.0)
        self.assertAlmostEqual(sma.value, 2.0)

        # next update should drop 1.0 and average 2,3,4
        self.assertAlmostEqual(sma.update(4.0), 3.0)
        self.assertAlmostEqual(sma.value, 3.0)

        # next update should drop 2.0 and average 3,4,5
        self.assertAlmostEqual(sma.update(5.0), 4.0)

    def test_reset_clears_state(self) -> None:
        sma = RollingSMA(window=2)
        sma.update(10.0)
        sma.update(20.0)
        self.assertTrue(sma.is_ready())

        sma.reset()
        self.assertFalse(sma.is_ready())
        self.assertAlmostEqual(sma.value, 0.0)

        self.assertAlmostEqual(sma.update(5.0), 5.0)
