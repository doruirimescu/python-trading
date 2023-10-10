import unittest
from typing import List
from Trading.utils.calculations import (calculate_percentage_losers,
                                        calculate_sharpe_ratio,
                                        calculate_max_consecutive_losers,
                                        calculate_cumulative_returns,
                                        calculate_max_drawdown,
                                        calculate_net_profit_eur,
                                        count_zero_crossings,
                                        count_probability_price_greater,
                                        count_probability_price_lower,
                                        count_probability_n_highs_in_a_row,
                                        count_probability_n_lows_in_a_row,
                                        count_probability_p_increment,
                                        count_average_decrement_given_n_highs_in_row)


class ReturnsCalculationsTest(unittest.TestCase):
    def test_calculate_sharpe_ratio(self):
        returns = [1, 2, 3, -1, -2, -3]
        r = calculate_sharpe_ratio(returns)
        self.assertEqual(0, r)

        returns = [1, 2, 3, -1, -2, 4]
        r = calculate_sharpe_ratio(returns)
        self.assertEqual(0.55, r)

    def test_calculate_percentage_losers(self):
        returns = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p = calculate_percentage_losers(returns)
        self.assertEqual(0.0, p)

        returns = [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]
        p = calculate_percentage_losers(returns)
        self.assertEqual(1.0, p)

        returns = [1, 2, 3, -1, -2, -3]
        p = calculate_percentage_losers(returns)
        self.assertEqual(0.5, p)

        returns = [1, -2, -3, -4, -5, -6, -7, -8, -9, -10]
        p = calculate_percentage_losers(returns)
        self.assertEqual(0.9, p)

    def test_calculate_max_consecutive_losers(self):
        returns = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        m = calculate_max_consecutive_losers(returns)
        self.assertEqual(0, m)

        returns = [-1, -2, -3, -4, 5, 6, 7, 8, 9, 10]
        m = calculate_max_consecutive_losers(returns)
        self.assertEqual(4, m)


        returns = [-1, 2, -3, -4, 5, -6, 7, -8, -9, -10]
        m = calculate_max_consecutive_losers(returns)
        self.assertEqual(3, m)

        returns = [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]
        m = calculate_max_consecutive_losers(returns)
        self.assertEqual(10, m)

        returns = [-1, -2, -3, -4, -5, -6, -7, -8, 9, -10]
        m = calculate_max_consecutive_losers(returns)
        self.assertEqual(8, m)

    def test_calculate_cumulative_returns(self):
        returns = [1, 0, 0, 1]
        c = calculate_cumulative_returns(returns)
        self.assertEqual([1, 1, 1, 2], c)

        returns = [-1, 1, -1, 1]
        c = calculate_cumulative_returns(returns)
        self.assertEqual([-1, 0, -1, 0], c)

        returns = [-1, 1, 2, 3, -5]
        c = calculate_cumulative_returns(returns)
        self.assertEqual([-1, 0, 2, 5, 0], c)

    def test_calculate_max_drawdown(self):
        returns = [1, 0, 0, 1]
        m = calculate_max_drawdown(returns)
        self.assertEqual(1, m)

        returns = [-1, 1, -1, 1]
        m = calculate_max_drawdown(returns)
        self.assertEqual(-1, m)

        returns = [-1, -1, -1, 1]
        m = calculate_max_drawdown(returns)
        self.assertEqual(-3, m)

    def test_calculate_net_profit_eur(self):
        #DAX30
        result = calculate_net_profit_eur(
            open_price=15614.6,
            close_price=15600,
            contract_value=25 * 0.01,
            quote_currency_to_eur_conversion_rate=1.0,
            cmd=1)
        self.assertAlmostEqual(3.65, result, 2)

        result = calculate_net_profit_eur(
            open_price=15600,
            close_price=15614.6,
            contract_value=25 * 0.01,
            quote_currency_to_eur_conversion_rate=1.0,
            cmd=1)
        self.assertAlmostEqual(-3.65, result, 2)

        result = calculate_net_profit_eur(
            open_price=15614.6,
            close_price=15600,
            contract_value=25 * 0.01,
            quote_currency_to_eur_conversion_rate=1.0,
            cmd=0)
        self.assertAlmostEqual(-3.65, result, 2)

        #EURUSD
        result = calculate_net_profit_eur(
            open_price=1.06131,
            close_price=1.07,
            contract_value=1000,
            quote_currency_to_eur_conversion_rate=1.0/1.06131,
            cmd=0)
        result = round(result, 2)
        self.assertAlmostEqual(8.19, result, 2)

        #NATGAS
        result = calculate_net_profit_eur(
            open_price=2.864,
            close_price=3.0,
            contract_value=30000*0.01,
            quote_currency_to_eur_conversion_rate=1.0/1.06166,
            cmd=0)
        result = round(result, 2)
        self.assertAlmostEqual(38.43, result, 2)

    def test_count_zero_crossings(self):
        result = count_zero_crossings([])
        self.assertEqual(0, result)

        result = count_zero_crossings([1, 2, 3, 4])
        self.assertEqual(0, result)

        result = count_zero_crossings([-1, -2 ,-3, -4])
        self.assertEqual(0, result)

        result = count_zero_crossings([1, -2, -3, -4])
        self.assertEqual(1, result)

        result = count_zero_crossings([1, -2, -3, -4])
        self.assertEqual(1, result)

        result = count_zero_crossings([1, 2, 3, -4])
        self.assertEqual(1, result)

        result = count_zero_crossings([1, -2, 3, -4])
        self.assertEqual(3, result)

        result = count_zero_crossings([-1, 2, -3, 4])
        self.assertEqual(3, result)

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

    def test_count_probability_p_increment(self):
        prices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = count_probability_p_increment(prices, 0)
        self.assertEqual(0.9, result)

        prices = [100, 120, 140]
        result = count_probability_p_increment(prices, 20)
        self.assertEqual(1/3, result)

        prices = [100, 120, 100, 111]
        result = count_probability_p_increment(prices, 10)
        self.assertEqual(0.5, result)

    def test_count_average_decrement_given_n_highs_in_row(self):
        prices = [1, 2]
        result = count_average_decrement_given_n_highs_in_row(prices, 1)
        self.assertEqual(0, result)

        prices = [1, 2, 1]
        result = count_average_decrement_given_n_highs_in_row(prices, 1)
        self.assertEqual(0.5, result)

        prices = [1, 2, 3, 1]
        result = count_average_decrement_given_n_highs_in_row(prices, 1)
        self.assertEqual(2/3, result)

        prices = [1, 2, 3, 1, 2, 3, 0]
        result = count_average_decrement_given_n_highs_in_row(prices, 1)
        self.assertEqual((2/3 + 1)/2, result)
