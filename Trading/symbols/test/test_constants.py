from unittest import TestCase
from Trading.symbols.constants import (
    XTB_ALL_SYMBOLS, XTB_STOCK_SYMBOLS, XTB_STOCK_TICKERS)

class TestConstants(TestCase):
    def test_c(self):
        self.assertGreaterEqual(5868, len(XTB_ALL_SYMBOLS))
        self.assertIn("AAPL.US_9", XTB_STOCK_SYMBOLS)
        self.assertIn("AAPL", XTB_STOCK_TICKERS)
