import unittest
from Trading.live.hedge.data import get_filename
from Trading.config.config import DATA_STORAGE_PATH


class TestGetFilename(unittest.TestCase):
    def test_get_filename(self):
        result = get_filename('EURUSD', 'EURRON')
        self.assertEqual(result, DATA_STORAGE_PATH + "hedging_correlation/" + "EURUSD_EURRON.json")

        result = get_filename('EURUSD', 'EURRON', "_test")
        self.assertEqual(result, DATA_STORAGE_PATH + "hedging_correlation/" + "EURUSD_EURRON_test.json")
