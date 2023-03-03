import unittest
from unittest import mock
from Trading.live.hedge.data import get_prices_from_file
from mock import patch
import pathlib

FIRST_PRICE_REFERENCED_DATA = str(pathlib.Path(__file__).parent.resolve()) + "/"


class TestGetFilename(unittest.TestCase):
    @patch('Trading.live.hedge.data.DATA_STORAGE_PATH', FIRST_PRICE_REFERENCED_DATA)
    def test_get_prices_from_file(self):

        result = get_prices_from_file("AUDUSD", "NZDUSD", 1, 1)
        self.assertEqual(tuple, type(result))

        pair_1_o, pair_2_o, net_profits = result
        self.assertEqual(300, len(pair_2_o))
        self.assertEqual(len(pair_1_o), len(pair_2_o))
        self.assertEqual(len(pair_1_o), len(net_profits))
