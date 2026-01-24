import unittest

from mrscore.components.volatility import EWMAVol


class TestEWMAVol(unittest.TestCase):
    def test_import_from_package(self) -> None:
        self.assertTrue(callable(EWMAVol))

    def test_warmup_uses_running_mean_of_r2(self) -> None:
        vol = EWMAVol(span=3, min_periods=2)
        self.assertFalse(vol.is_ready())

        # first sample: sigma2 = r^2 = 4, vol = 2
        self.assertAlmostEqual(vol.update(2.0), 2.0)
        self.assertFalse(vol.is_ready())

        # second sample: mean r^2 = (4+16)/2=10 -> vol = sqrt(10)
        self.assertAlmostEqual(vol.update(4.0), 10.0 ** 0.5)
        self.assertTrue(vol.is_ready())

    def test_ewma_recursion_after_warmup(self) -> None:
        vol = EWMAVol(span=4, min_periods=1)
        # warmup: sigma2 = 9
        self.assertAlmostEqual(vol.update(3.0), 3.0)

        lam = 1.0 - (2.0 / (4 + 1.0))
        expected_sigma2 = lam * 9.0 + (1.0 - lam) * (5.0 ** 2)
        expected_vol = expected_sigma2 ** 0.5
        self.assertAlmostEqual(vol.update(5.0), expected_vol)

    def test_min_volatility_floor(self) -> None:
        vol = EWMAVol(span=2, min_periods=1, min_volatility=0.5)
        self.assertAlmostEqual(vol.update(0.0), 0.5)

    def test_reset_clears_state(self) -> None:
        vol = EWMAVol(span=2, min_periods=2)
        vol.update(1.0)
        vol.update(2.0)
        self.assertTrue(vol.is_ready())

        vol.reset()
        self.assertFalse(vol.is_ready())
        self.assertAlmostEqual(vol.value, 0.0)
