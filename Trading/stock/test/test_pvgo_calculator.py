import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock


if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = types.ModuleType("yfinance")

pvgo = importlib.import_module("Trading.stock.pvgo_calculator")


class PvgoCalculatorTest(unittest.TestCase):
    def setUp(self):
        pvgo.yf.Ticker = MagicMock()

    def test_fetches_stock_fundamentals_from_one_info_object(self):
        ticker = MagicMock()
        ticker.info = {
            "currentPrice": 200,
            "forwardEps": 10,
            "beta": 1.2,
        }
        pvgo.yf.Ticker.return_value = ticker

        result = pvgo.fetch_pvgo_fundamentals("aapl")

        self.assertEqual(
            result,
            {"current_price": 200.0, "forward_eps": 10.0, "beta": 1.2},
        )
        pvgo.yf.Ticker.assert_called_once_with("aapl")

    def test_fetches_treasury_yield_from_fast_info(self):
        ticker = MagicMock()
        ticker.fast_info = {"lastPrice": 4.25}
        pvgo.yf.Ticker.return_value = ticker

        result = pvgo.fetch_risk_free_rate()

        self.assertEqual(result, 0.0425)
        pvgo.yf.Ticker.assert_called_once_with("^TNX")

    def test_uses_previous_close_when_last_treasury_price_is_unavailable(self):
        ticker = MagicMock()
        ticker.fast_info = {"previousClose": 4.1}
        pvgo.yf.Ticker.return_value = ticker

        result = pvgo.fetch_risk_free_rate()

        self.assertAlmostEqual(result, 0.041)

    def test_computes_without_yfinance_calls(self):
        result = pvgo.compute_pvgo(
            {"current_price": 200.0, "forward_eps": 10.0, "beta": 1.2},
            risk_free_rate=0.04,
            ticker_symbol="aapl",
            market_risk_premium=0.05,
        )

        self.assertEqual(result["Ticker"], "AAPL")
        self.assertEqual(result["Cost of Equity"], "10.00%")
        self.assertEqual(result["No-Growth Value"], "$100.00")
        self.assertEqual(result["PVGO"], "$100.00")
        self.assertEqual(result["PVGO Percentage"], "50.00%")
        pvgo.yf.Ticker.assert_not_called()

    def test_rejects_non_positive_cost_of_equity(self):
        result = pvgo.compute_pvgo(
            {"current_price": 200.0, "forward_eps": 10.0, "beta": 0.0},
            risk_free_rate=0.0,
            ticker_symbol="AAPL",
        )

        self.assertEqual(
            result,
            "Error calculating PVGO: Cost of equity must be positive.",
        )


if __name__ == "__main__":
    unittest.main()
