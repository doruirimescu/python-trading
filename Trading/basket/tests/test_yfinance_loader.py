import unittest
from unittest import mock

import numpy as np

from mrscore.io.history import History
from mrscore.io.yfinance_loader import YFinanceLoadRequest, YFinanceLoader, _history_from_single_df


class _FakeSeries:
    def __init__(self, data):
        self._data = np.asarray(data, dtype=np.float64)

    def to_numpy(self, dtype=None, copy=False):
        if dtype is None:
            return self._data
        return self._data.astype(dtype, copy=copy)


class _FakeIndex:
    def __init__(self, dates):
        self._dates = np.asarray(dates)

    def to_numpy(self, dtype=None):
        if dtype is None:
            return self._dates
        return self._dates.astype(dtype)


class _FakeDF:
    def __init__(self, *, columns, index, data, empty=False):
        self.columns = columns
        self.index = index
        self._data = data
        self.empty = empty

    def __getitem__(self, key):
        return _FakeSeries(self._data[key])


class TestYFinanceLoader(unittest.TestCase):
    def test_history_from_single_df_builds_fields(self) -> None:
        # Helper: converts a single-ticker dataframe into a History with OHLC arrays.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        df = _FakeDF(
            columns=["Open", "High", "Low", "Close"],
            index=_FakeIndex(dates),
            data={
                "Open": [1.0, 2.0],
                "High": [2.0, 3.0],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
            },
        )

        history = _history_from_single_df("TEST", dates, df)
        self.assertIsInstance(history, History)
        self.assertTrue(np.array_equal(history.dates, dates))
        self.assertTrue(np.array_equal(history.open, np.array([1.0, 2.0])))
        self.assertTrue(np.array_equal(history.high, np.array([2.0, 3.0])))
        self.assertTrue(np.array_equal(history.low, np.array([0.5, 1.5])))
        self.assertTrue(np.array_equal(history.close, np.array([1.5, 2.5])))

    def test_history_from_single_df_missing_ohlc_raises(self) -> None:
        # Helper: missing all OHLC columns should fail fast.
        dates = np.array(["2024-01-01"], dtype="datetime64[D]")
        df = _FakeDF(
            columns=["Volume"],
            index=_FakeIndex(dates),
            data={"Volume": [1000]},
        )
        with self.assertRaises(ValueError):
            _history_from_single_df("TEST", dates, df)

    def test_loader_rejects_empty_tickers(self) -> None:
        # Helper: loader enforces non-empty ticker list.
        loader = YFinanceLoader()
        req = YFinanceLoadRequest(tickers=[])
        with self.assertRaises(ValueError):
            loader.load(req)

    def test_loader_single_ticker_path(self) -> None:
        # Helper: single-ticker download uses the non-MultiIndex path.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        df = _FakeDF(
            columns=["Open", "High", "Low", "Close"],
            index=_FakeIndex(dates),
            data={
                "Open": [1.0, 2.0],
                "High": [2.0, 3.0],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
            },
        )

        fake_yf = mock.Mock()
        fake_yf.download.return_value = df

        loader = YFinanceLoader()
        req = YFinanceLoadRequest(tickers=["TEST"])

        with mock.patch.dict("sys.modules", {"yfinance": fake_yf}):
            out = loader.load(req)

        self.assertIn("TEST", out)
        self.assertIsInstance(out["TEST"], History)
        self.assertTrue(np.array_equal(out["TEST"].dates, dates))

    def test_loader_raises_on_empty_download(self) -> None:
        # Helper: loader raises when yfinance returns no data.
        dates = np.array(["2024-01-01"], dtype="datetime64[D]")
        df = _FakeDF(columns=["Open"], index=_FakeIndex(dates), data={"Open": [1.0]}, empty=True)

        fake_yf = mock.Mock()
        fake_yf.download.return_value = df

        loader = YFinanceLoader()
        req = YFinanceLoadRequest(tickers=["TEST"])

        with mock.patch.dict("sys.modules", {"yfinance": fake_yf}):
            with self.assertRaises(ValueError):
                loader.load(req)
