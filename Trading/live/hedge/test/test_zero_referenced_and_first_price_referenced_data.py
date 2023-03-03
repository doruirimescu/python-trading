import unittest
from Trading.utils.write_to_file import read_json_file
from Trading.utils.calculations import calculate_mean
from Trading.live.hedge.data import normalize_zero_referenced_profits
import pathlib

FIRST_PRICE_REFERENCED_DATA = pathlib.Path(__file__).parent.resolve().joinpath("AUDUSD_NZDUSD_test_first_price_ref.json")
ZERO_PRICE_REFERENCED_DATA = pathlib.Path(__file__).parent.resolve().joinpath("AUDUSD_NZDUSD_test_zero_price_ref.json")


FIRST_REFERENCED_DATA = read_json_file(FIRST_PRICE_REFERENCED_DATA)
ZERO_REFERENCED_DATA = read_json_file(ZERO_PRICE_REFERENCED_DATA)


def zip_data(key_1: str, key_2: str):
    return zip(FIRST_REFERENCED_DATA[key_1], ZERO_REFERENCED_DATA[key_2])


def normalize_zero_referenced_data():
    first_zero_referenced_net_profit = ZERO_REFERENCED_DATA['net_profits'][0]
    return [p - first_zero_referenced_net_profit for p in ZERO_REFERENCED_DATA['net_profits']]


class TestData(unittest.TestCase):
    def test_price_data_is_same(self):
        for date_1, date_2 in zip_data('dates', 'dates'):
            self.assertEqual(date_1, date_2)

        for p1, p2 in zip_data('AUDUSD', 'AUDUSD'):
            self.assertEqual(p1, p2)

        for p1, p2 in zip_data('NZDUSD', 'NZDUSD'):
            self.assertEqual(p1, p2)

    def test_net_profits_are_not_same(self):
        for p1, p2 in zip_data('net_profits', 'net_profits'):
            self.assertNotEqual(p1, p2)

    def test_net_profits_have_constant_offset(self):
        normalized_zero_data = normalize_zero_referenced_profits(ZERO_REFERENCED_DATA['net_profits'])

        diff = sum([abs(p-o) for o, p in zip(normalized_zero_data, FIRST_REFERENCED_DATA['net_profits'])])

        self.assertLessEqual(diff, 10.0)

        offset_mean = calculate_mean(normalized_zero_data)
        first_mean = calculate_mean(FIRST_REFERENCED_DATA['net_profits'])

        d = abs(offset_mean - first_mean)
        self.assertLessEqual(d, 1.0)
