from unittest import TestCase
from Trading.symbols.constants import XTB_ALL_SYMBOLS

class TestConstants(TestCase):
    def test_c(self):
        self.assertGreaterEqual(3862, len(XTB_ALL_SYMBOLS))
