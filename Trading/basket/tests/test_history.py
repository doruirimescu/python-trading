import unittest

import numpy as np

from mrscore.io.history import History, OHLC


class TestHistory(unittest.TestCase):
    def test_length_mismatch_raises(self) -> None:
        # Helper: ensure all OHLC arrays are same length as dates.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        open_ = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        with self.assertRaises(ValueError):
            History(symbol="TEST", dates=dates, open=open_)

    def test_field_returns_requested_series(self) -> None:
        # Helper: access the chosen OHLC field via the enum.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        close = np.array([10.0, 12.0], dtype=np.float64)
        history = History(symbol="TEST", dates=dates, close=close)
        self.assertTrue(np.array_equal(history.field(OHLC.CLOSE), close))

    def test_field_missing_raises(self) -> None:
        # Helper: missing fields should fail fast with a clear error.
        dates = np.array(["2024-01-01"], dtype="datetime64[D]")
        history = History(symbol="TEST", dates=dates)
        with self.assertRaises(ValueError):
            history.field(OHLC.HIGH)

    def test_normalize_creates_scaled_history(self) -> None:
        # Helper: normalize scales the chosen field by its first value.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        close = np.array([10.0, 15.0], dtype=np.float64)
        history = History(symbol="TEST", dates=dates, close=close)

        normalized = history.normalize(OHLC.CLOSE)
        self.assertEqual(normalized.symbol, "TEST")
        self.assertTrue(np.array_equal(normalized.dates, dates))
        self.assertTrue(np.allclose(normalized.close, np.array([1.0, 1.5])))
        # Only the normalized field should be present.
        self.assertIsNone(normalized.open)
        self.assertIsNone(normalized.high)
        self.assertIsNone(normalized.low)

    def test_normalize_raises_on_zero_base(self) -> None:
        # Helper: cannot normalize when the first value is zero.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        close = np.array([0.0, 2.0], dtype=np.float64)
        history = History(symbol="TEST", dates=dates, close=close)
        with self.assertRaises(ValueError):
            history.normalize(OHLC.CLOSE)
