from Trading.utils.range.range import calculate_rank
from Trading.model.history import History
import unittest

class TestRange(unittest.TestCase):
    def test_calculate_rank(self):
        history = History(
            symbol='AAPL',
            date=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'],
            high=[105, 105, 105, 105, 105],
            low=[95, 95, 95, 95, 95],
        )
        rank = calculate_rank(history, 3)
        self.assertEqual(rank, 0.0)

        history = History(
            symbol='AAPL',
            date=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'],
            high=[105, 105, 110, 110, 100],
            low=[100, 100, 100, 100, 100],
        )
        rank = calculate_rank(history, 5)
        self.assertEqual(rank, 2.0)

        history = History(
                symbol='AAPL',
                high=[10, 20, 30, 40, 50],
                low=[0, 10, 20, 30, 40],
            )
        rank = calculate_rank(history, 5)
        self.assertEqual(rank, 4.0)
