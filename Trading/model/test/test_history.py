from unittest import TestCase
from Trading.model.history import History
from datetime import datetime


class TestHistory(TestCase):
    def test_init(self):
        history = History()
        self.assertIsNone(history.symbol)
        self.assertIsNone(history.timeframe)
        self.assertIsNone(history.date)
        self.assertIsNone(history.open)
        self.assertIsNone(history.high)
        self.assertIsNone(history.low)
        self.assertIsNone(history.close)

    def test_slice(self):
        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            open=[1.2, 1.3, 1.4],
            high=[1.3, 1.4, 1.5],
            low=[1.1, 1.2, 1.3],
            close=[1.3, 1.4, 1.5],
        )
        sliced = history.slice(1, 3)
        self.assertEqual(sliced.symbol, "EURUSD")
        self.assertEqual(sliced.timeframe, "1M")
        self.assertEqual(sliced.date, [datetime(2021, 1, 2), datetime(2021, 1, 3)])
        self.assertEqual(sliced.open, [1.3, 1.4])
        self.assertEqual(sliced.high, [1.4, 1.5])
        self.assertEqual(sliced.low, [1.2, 1.3])
        self.assertEqual(sliced.close, [1.4, 1.5])

        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
            ],
            open=[1.2, 1.3, 1.4, 1.5],
            high=[1.3, 1.4, 1.5, 1.5],
            low=[1.1, 1.2, 1.3, 1.3],
            close=[1.3, 1.4, 1.5, 1.5],
        )
        sliced = history.slice(-2)
        self.assertEqual(sliced.symbol, "EURUSD")
        self.assertEqual(sliced.timeframe, "1M")
        self.assertEqual(sliced.date, [datetime(2021, 1, 3), datetime(2021, 1, 4)])
        self.assertEqual(sliced.open, [1.4, 1.5])
        self.assertEqual(sliced.high, [1.5, 1.5])
        self.assertEqual(sliced.low, [1.3, 1.3])
        self.assertEqual(sliced.close, [1.5, 1.5])

    def test_slice_n_candles_before_date(self):
        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
            ],
            open=[1.2, 1.3, 1.4, 1.5],
            high=[1.3, 1.4, 1.5, 1.5],
            low=[1.1, 1.2, 1.3, 1.3],
            close=[1.3, 1.4, 1.5, 1.5],
        )
        sliced = history.slice_n_candles_before_date(datetime(2021, 1, 3), 2)
        print(sliced)
        self.assertEqual(sliced.symbol, "EURUSD")
        self.assertEqual(sliced.timeframe, "1M")
        self.assertEqual(sliced.date, [datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)])
        self.assertEqual(sliced.open, [1.2, 1.3, 1.4])
        self.assertEqual(sliced.high, [1.3, 1.4, 1.5])
        self.assertEqual(sliced.low, [1.1, 1.2, 1.3])
        self.assertEqual(sliced.close, [1.3, 1.4, 1.5])

    def test_extend(self):
        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)],
            open=[1.2, 1.3, 1.4],
            high=[1.3, 1.4, 1.5],
            low=[1.1, 1.2, 1.3],
            close=[1.3, 1.4, 1.5],
        )
        history2 = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[datetime(2021, 1, 4), datetime(2021, 1, 5), datetime(2021, 1, 6)],
            open=[1.5, 1.6, 1.7],
            high=[1.6, 1.7, 1.8],
            low=[1.4, 1.5, 1.6],
            close=[1.6, 1.7, 1.8],
        )
        history.extend(history2)
        self.assertEqual(history.symbol, "EURUSD")
        self.assertEqual(history.timeframe, "1M")
        self.assertEqual(
            history.date,
            [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
                datetime(2021, 1, 6),
            ],
        )
        self.assertEqual(history.open, [1.2, 1.3, 1.4, 1.5, 1.6, 1.7])
        self.assertEqual(history.high, [1.3, 1.4, 1.5, 1.6, 1.7, 1.8])
        self.assertEqual(history.low, [1.1, 1.2, 1.3, 1.4, 1.5, 1.6])
        self.assertEqual(history.close, [1.3, 1.4, 1.5, 1.6, 1.7, 1.8])

        # test that duplicates are removed
        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3), datetime(2022, 1, 1)],
            open= [1.2, 1.3, 1.4, 1.5],
            high= [1.3, 1.4, 1.5, 1.6],
            low=  [1.1, 1.2, 1.01, 1.4],
            close=[1.3, 1.4, 1.9, 1.6],
        )
        history.extend(history2)
        self.assertEqual(history.symbol, "EURUSD")
        self.assertEqual(history.timeframe, "1M")
        self.assertEqual(
            history.date,
            [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5),
                datetime(2021, 1, 6),
                datetime(2022, 1, 1),
            ],
        )
        self.assertEqual(history.open, [1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.5])
        self.assertEqual(history.high, [1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.6])
        self.assertEqual(history.low, [1.1, 1.2, 1.01, 1.4, 1.5, 1.6, 1.4])
        self.assertEqual(history.close, [1.3, 1.4, 1.9, 1.6, 1.7, 1.8, 1.6])

    def test_sort_by_dates(self):
        history = History(
            symbol="EURUSD",
            timeframe="1M",
            date=[datetime(2021, 1, 3), datetime(2021, 1, 1), datetime(2021, 1, 2)],
            open=[1.4, 1.2, 1.3],
            high=[1.5, 1.3, 1.4],
            low=[1.3, 1.1, 1.2],
            close=[1.5, 1.3, 1.4],
        )
        history.sort_by_dates()
        self.assertEqual(
            history.date, [datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)]
        )
        self.assertEqual(history.open, [1.2, 1.3, 1.4])
        self.assertEqual(history.high, [1.3, 1.4, 1.5])
        self.assertEqual(history.low, [1.1, 1.2, 1.3])
        self.assertEqual(history.close, [1.3, 1.4, 1.5])
