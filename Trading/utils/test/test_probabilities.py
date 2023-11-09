import unittest
from Trading.utils.probability import (
    count_probability_price_greater,
    count_probability_price_lower,
    count_probability_n_highs_in_a_row,
    count_probability_n_lows_in_a_row,
    count_probability_return,
    count_average_decrement_given_n_highs_in_row,
    get_max_return,
    get_min_return,
    get_median_return,
    get_average_return
)

class TestProbability(unittest.TestCase):
    def test_count_probability_price_greater(self):
        prices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        result = count_probability_price_greater(prices, 10)
        self.assertEqual(0, result)

        result = count_probability_price_greater(prices, 9)
        self.assertEqual(0.1, result)

        result = count_probability_price_greater(prices, 8)
        self.assertEqual(0.2, result)

    def test_count_probability_price_lower(self):
        prices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        result = count_probability_price_lower(prices, 10)
        self.assertEqual(1, result)

        result = count_probability_price_lower(prices, 9)
        self.assertEqual(0.9, result)

        result = count_probability_price_lower(prices, 8)
        self.assertEqual(0.8, result)

    def test_count_probability_n_highs_in_a_row(self):
        prices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(0.9, result)

        result = count_probability_n_highs_in_a_row(prices, 5)
        self.assertEqual(0.5, result)

        result = count_probability_n_highs_in_a_row(prices, 9)
        self.assertEqual(0.1, result)

        prices = [0, 0, 0, 0 ,0]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(0.0, result)

        prices = [0, 0, 0, 0, 1]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, 0, 0, 1, 1]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, 0, 2, 1, 1]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, 1, 2, 4, 5]
        result = count_probability_n_highs_in_a_row(prices, 1)
        self.assertEqual(4/5, result)

    def test_count_probability_n_lows_in_a_row(self):
        prices = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(0.9, result)

        result = count_probability_n_lows_in_a_row(prices, 5)
        self.assertEqual(0.5, result)

        result = count_probability_n_lows_in_a_row(prices, 9)
        self.assertEqual(0.1, result)

        prices = [0, 0, 0, 0 ,0]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(0.0, result)

        prices = [0, 0, 0, 0, -1]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, 0, 0, -1, -1]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, 0, -2, -1, -1]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(1/5, result)

        prices = [0, -1, -2, -4, -5]
        result = count_probability_n_lows_in_a_row(prices, 1)
        self.assertEqual(4/5, result)

    def test_get_max_return(self):
        prices = [1, 1.1, 1.0, 1.3, 1.0]
        result = round(get_max_return(prices), 2)
        self.assertEqual(0.3, result)

    def test_get_min_return(self):
        prices = [1, 1.1, 1.0, 1.3, 1.0]
        result = round(get_min_return(prices), 2)
        self.assertEqual(-0.23, result)

    def test_count_probability_return(self):
        prices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = count_probability_return(prices, 0)
        self.assertEqual(0.9, result)

        prices = [100, 120, 140]
        result = count_probability_return(prices, 0.2)
        self.assertEqual(1/3, result)

        prices = [100, 120, 100, 111]
        result = count_probability_return(prices, 0.1)
        self.assertEqual(0.5, result)

    def test_get_median_return(self):
        prices = [1, 1.1, 1, 1.3]
        result = round(get_median_return(prices), 2)
        self.assertEqual(0.1, result)

    # def test_count_average_decrement_given_n_highs_in_row(self):
    #     prices = [1, 2]
    #     result = count_average_decrement_given_n_highs_in_row(prices, 1)
    #     self.assertEqual(0, result)

    #     prices = [1, 2, 1]
    #     result = count_average_decrement_given_n_highs_in_row(prices, 1)
    #     self.assertEqual(0.5, result)

    #     prices = [1, 2, 3, 1]
    #     result = count_average_decrement_given_n_highs_in_row(prices, 1)
    #     self.assertEqual(2/3, result)

    #     prices = [1, 2, 3, 1, 2, 3, 0]
    #     result = count_average_decrement_given_n_highs_in_row(prices, 1)
    #     self.assertEqual((2/3 + 1)/2, result)
