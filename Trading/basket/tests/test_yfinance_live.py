import os
import unittest

from mrscore.io.yfinance_loader import YFinanceLoadRequest, YFinanceLoader


class TestYFinanceLive(unittest.TestCase):
    def test_download_three_tickers(self) -> None:
        # Helper: live download to validate integration against yfinance.
        # Skip unless explicitly enabled to avoid flaky CI/network failures.
        if os.environ.get("MR_SCORE_LIVE_YF") != "1":
            self.skipTest("Set MR_SCORE_LIVE_YF=1 to run live yfinance download")

        loader = YFinanceLoader()
        req = YFinanceLoadRequest(
            tickers=["AAPL", "MSFT", "GOOG"],
            period="1mo",
            interval="1d",
            auto_adjust=True,
        )
        out = loader.load(req)

        self.assertEqual(set(out.keys()), {"AAPL", "MSFT", "GOOG"})
        # print
        print(out["AAPL"])
        for ticker, history in out.items():
            # Basic sanity checks on returned History objects
            self.assertEqual(history.symbol, ticker)
            self.assertGreater(len(history.dates), 0)
            # Expect at least one OHLC field to be present
            self.assertTrue(
                any(
                    field is not None
                    for field in (history.open, history.high, history.low, history.close)
                )
            )
