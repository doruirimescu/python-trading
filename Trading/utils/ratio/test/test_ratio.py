import unittest

from Trading.utils.ratio.ratio import Ratio, DateNotFoundError
from Trading.model.history import History
from datetime import datetime

HISTORY_A = History(
    **{
        "date": [datetime(2021, 1, 1), datetime(2021, 1, 2)],
        "open": [1, 2],
        "close": [1, 2],
        "high": [1, 2],
        "low": [1, 2],
    }
)
HISTORY_B = History(
    **{
        "date": [datetime(2021, 1, 1), datetime(2021, 1, 2)],
        "open": [1, 2],
        "close": [2, 3],
        "high": [2, 3],
        "low": [1, 2],
    }
)


class TestRatio(unittest.TestCase):
    def test_constructor(self):
        # test assert is instance
        with self.assertRaises(ValueError):
            Ratio(["a", "b"], ["b"])
        with self.assertRaises(ValueError):
            Ratio(1, ["b"])
        with self.assertRaises(ValueError):
            Ratio(["b"], 1)
        with self.assertRaises(ValueError):
            Ratio([], ["a"])
        with self.assertRaises(ValueError):
            Ratio(["a"], [])

        r = Ratio(["a"], ["b"])
        self.assertEqual(r.numerator, ["a"])
        self.assertEqual(r.denominator, ["b"])
        self.assertEqual(r.mean, None)
        self.assertEqual(r.std, None)
        self.assertEqual(r.histories, dict())
        self.assertEqual(r.dates, [])

    def test_add_histories(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        self.assertEqual(r.histories["a"], HISTORY_A)
        self.assertEqual(r.histories["b"], HISTORY_B)

    def test_get_get_numerator_histories(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        self.assertEqual(r.get_numerator_prices_at_date(datetime(2021, 1, 1)), [1])
        self.assertEqual(r.get_numerator_prices_at_date(datetime(2021, 1, 2)), [2])

    def test_get_get_denominator_histories(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        self.assertEqual(r.get_denominator_prices_at_date(datetime(2021, 1, 1)), [2])
        self.assertEqual(r.get_denominator_prices_at_date(datetime(2021, 1, 2)), [3])

    def test_get_numerator_prices_at_date(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        self.assertEqual(r.get_numerator_prices_at_date(datetime(2021, 1, 1)), [1])
        self.assertEqual(r.get_numerator_prices_at_date(datetime(2021, 1, 2)), [2])

    def test_get_denominator_prices_at_date(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        self.assertEqual(r.get_denominator_prices_at_date(datetime(2021, 1, 1)), [2])
        self.assertEqual(r.get_denominator_prices_at_date(datetime(2021, 1, 2)), [3])

    def test_eliminate_nonintersecting_dates(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        r.eliminate_nonintersecting_dates()
        self.assertEqual(r.dates, [datetime(2021, 1, 1), datetime(2021, 1, 2)])
        self.assertEqual(r.histories["a"], HISTORY_A)
        self.assertEqual(r.histories["b"], HISTORY_B)
        history_c = {"date": [datetime(2021, 1, 5)], "close": [100]}
        r.add_history("c", history_c)
        r.eliminate_nonintersecting_dates()
        self.assertEqual(r.dates, [datetime(2021, 1, 1), datetime(2021, 1, 2)])

    def test_calculate_ratio(self):
        r = Ratio(["a"], ["b"])
        r.add_history("a", HISTORY_A)
        r.add_history("b", HISTORY_B)
        r.eliminate_nonintersecting_dates()
        r.calculate_ratio()
        normalized_numerator = [1, 2]
        normalized_denominator = [2 / 2, 3 / 2]
        self.assertEqual(r.normalized_histories["a"].open, normalized_numerator)
        self.assertEqual(r.normalized_histories["b"].close, normalized_denominator)
        self.assertAlmostEqual(r.mean, (1 + 4 / 3) / 2, 2)

    def test_calculate_ratio_two_symbols(self):
        num_1 = History(
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            close=[1, 2, 3],
            open=[1, 2, 3],
            high=[1, 2, 3],
            low=[1, 2, 3],
        )
        num_2 = History(
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            close=[1, 2, 3],
            open=[1, 2, 3],
            high=[1, 2, 3],
            low=[1, 2, 3],
        )
        den_1 = History(
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            close=[2, 3, 4],
            open=[1, 2, 3],
            high=[1, 2, 3],
            low=[1, 2, 3],
        )
        den_2 = History(
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            close=[2, 3, 4],
            open=[1, 2, 3],
            high=[1, 2, 3],
            low=[1, 2, 3],
        )
        r = Ratio(["num_1", "num_2"], ["den_1", "den_2"])
        r.add_history("num_1", num_1)
        r.add_history("num_2", num_2)
        r.add_history("den_1", den_1)
        r.add_history("den_2", den_2)

        r.eliminate_nonintersecting_dates()
        r.calculate_ratio()
        normalied_num_1 = [c / num_1.close[0] for c in num_1.close]
        normalied_num_2 = [c / num_2.close[0] for c in num_2.close]
        normalied_den_1 = [c / den_1.close[0] for c in den_1.close]
        normalied_den_2 = [c / den_2.close[0] for c in den_2.close]
        self.assertEqual(r.normalized_histories["num_1"].close, normalied_num_1)
        self.assertEqual(r.normalized_histories["num_2"].close, normalied_num_2)
        self.assertEqual(r.normalized_histories["den_1"].close, normalied_den_1)
        self.assertEqual(r.normalized_histories["den_2"].close, normalied_den_2)

        ratio_values = list()
        for i in range(3):
            ratio_values.append(
                (normalied_num_1[i] + normalied_num_2[i])
                / (normalied_den_1[i] + normalied_den_2[i])
            )
        self.assertEqual(r.ratio_values, ratio_values)

    def test_get_next_date_at_mean(self):
        r = Ratio(["num"], ["den"])
        num = History(
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
            ],
            close=[1, 2, 4, 2, 1],
            open=[1, 2, 4, 2, 1],
            high=[1, 2, 4, 2, 1],
            low=[1, 2, 4, 2, 1],
        )
        den = History(
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
            ],
            close=[1, 1, 1, 1, 1],
            open=[1, 1, 1, 1, 1],
            high=[1, 1, 1, 1, 1],
            low=[1, 1, 1, 1, 1],
        )
        r.add_history("num", num)
        r.add_history("den", den)
        r.eliminate_nonintersecting_dates()
        r.calculate_ratio()
        self.assertEqual(
            r.get_next_date_at_mean(datetime(2021, 1, 1)),
            (
                datetime(2021, 1, 2),
                1,
            ),
        )
        self.assertEqual(
            r.get_next_date_at_mean(datetime(2021, 1, 2)), (datetime(2021, 1, 4), 3)
        )
        self.assertEqual(
            r.get_next_date_at_mean(datetime(2021, 1, 3)), (datetime(2021, 1, 4), 3)
        )
        with self.assertRaises(DateNotFoundError):
            r.get_next_date_at_mean(datetime(2021, 1, 4))

    def test_get_ratio_value_at_date(self):
        r = Ratio(["num"], ["den"])
        num = History(
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
            ],
            close=[1, 2, 4, 2, 1],
            open=[1, 2, 4, 2, 1],
            high=[1, 2, 4, 2, 1],
            low=[1, 2, 4, 2, 1],
        )
        den = History(
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
            ],
            close=[1, 1, 1, 1, 1],
            open=[1, 1, 1, 1, 1],
            high=[1, 1, 1, 1, 1],
            low=[1, 1, 1, 1, 1],
        )
        r.add_history("num", num)
        r.add_history("den", den)
        r.eliminate_nonintersecting_dates()
        r.calculate_ratio()
        self.assertEqual(r.get_ratio_value_at_date(datetime(2021, 1, 1)), 1)
        self.assertEqual(r.get_ratio_value_at_date(datetime(2021, 1, 2)), 2)
        self.assertEqual(r.get_ratio_value_at_date(datetime(2021, 1, 3)), 4)
        self.assertEqual(r.get_ratio_value_at_date(datetime(2021, 1, 4)), 2)
        self.assertEqual(r.get_ratio_value_at_date(datetime(2021, 1, 5)), 1)
