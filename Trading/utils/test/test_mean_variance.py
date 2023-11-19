import unittest
from Trading.utils.mean_variance import (
    AssetReturns,
    Portfolio,
    asset_covariance,
    asset_correlation,
)


class TestMeanVariance(unittest.TestCase):
    def test_asset_returns_mean(self):
        r1 = [0.5, 0.1, -0.1]
        r2 = [0, 0.3, -0.3]
        a1 = AssetReturns(r1, "a1")
        a2 = AssetReturns(r2, "a2")

        self.assertAlmostEqual(0.167, a1.mean(), 3)
        self.assertEqual(0, a2.mean())

        v1 = a1.variance()
        self.assertAlmostEqual(0.062, a1.variance(), 3)

        c12 = asset_covariance(a1, a2)
        self.assertAlmostEqual(0.02, c12, 3)

    def test_portfolio(self):
        r1 = [0.5, 0.1, -0.1]
        r2 = [0, 0.3, -0.3]
        a1 = AssetReturns(r1, "a1")
        a2 = AssetReturns(r2, "a2")

        w1 = 0.1
        w2 = 0.9
        p = Portfolio([a1, a2], [w1, w2])
        self.assertEqual(asset_covariance(a1, a2), asset_covariance(a2, a1))
        self.assertAlmostEqual(w1 * a1.mean() + w2 * a2.mean(), p.mean(), 3)

        # Confirm wiki formula for 2-asset portoflio variance
        # https://en.wikipedia.org/wiki/Modern_portfolio_theory
        self.assertAlmostEqual(
            w1 * w1 * a1.variance()
            + w2 * w2 * a2.variance()
            + 2
            * w1
            * w2
            * a1.standard_deviation()
            * a2.standard_deviation()
            * asset_correlation(a1, a2),
            p.variance(),
            3,
        )
