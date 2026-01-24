import unittest

from mrscore.components.volatility.rolling_std import RollingStd


class TestRollingStd(unittest.TestCase):
    def test_warmup_uses_available_samples(self) -> None:
        rs = RollingStd(window=3, min_periods=2, ddof=0)
        self.assertFalse(rs.is_ready())

        self.assertAlmostEqual(rs.update(1.0), 0.0)
        self.assertFalse(rs.is_ready())

        # mean=1.5, var=((1^2+2^2)-2*1.5^2)/2=0.25, std=0.5
        self.assertAlmostEqual(rs.update(2.0), 0.5)
        self.assertTrue(rs.is_ready())

    def test_rolls_over_window(self) -> None:
        rs = RollingStd(window=3, min_periods=1, ddof=0)
        rs.update(1.0)
        rs.update(2.0)
        rs.update(3.0)

        # next update drops 1.0 -> window [2,3,4]
        self.assertAlmostEqual(rs.update(4.0), 0.816496580927726)

        # next update drops 2.0 -> window [3,4,5]
        self.assertAlmostEqual(rs.update(5.0), 0.816496580927726)

    def test_ddof_one_requires_two_samples(self) -> None:
        rs = RollingStd(window=2, min_periods=1, ddof=1)
        # denom is zero with one sample -> min_volatility (0.0)
        self.assertAlmostEqual(rs.update(10.0), 0.0)
        self.assertTrue(rs.is_ready())

        # with two samples: mean=15, var=((100+400)-2*225)/1=50, std~7.0711
        self.assertAlmostEqual(rs.update(20.0), 7.0710678118654755)

    def test_min_volatility_applies(self) -> None:
        rs = RollingStd(window=3, min_periods=1, ddof=0, min_volatility=0.1)
        self.assertAlmostEqual(rs.update(5.0), 0.1)
        self.assertAlmostEqual(rs.update(5.0), 0.1)

    def test_reset_clears_state(self) -> None:
        rs = RollingStd(window=2, min_periods=2, ddof=0)
        rs.update(1.0)
        rs.update(3.0)
        self.assertTrue(rs.is_ready())

        rs.reset()
        self.assertFalse(rs.is_ready())
        self.assertAlmostEqual(rs.value, 0.0)

        self.assertAlmostEqual(rs.update(2.0), 0.0)
