import unittest

import numpy as np

from mrscore.io.adapters import AlignedPanel


class TestAlignedPanel(unittest.TestCase):
    def test_construction_and_fields(self) -> None:
        # Helper: create a small aligned panel and verify core fields.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        symbols = ["AAA", "BBB"]
        values = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)

        panel = AlignedPanel(dates=dates, symbols=symbols, values=values)
        self.assertTrue(np.array_equal(panel.dates, dates))
        self.assertEqual(panel.symbols, symbols)
        self.assertTrue(np.array_equal(panel.values, values))

    def test_values_shape_matches_dates_and_symbols(self) -> None:
        # Helper: ensure values matrix shape matches (T, N).
        dates = np.array(["2024-01-01", "2024-01-02", "2024-01-03"], dtype="datetime64[D]")
        symbols = ["AAA", "BBB", "CCC"]
        values = np.zeros((3, 3), dtype=np.float64)

        panel = AlignedPanel(dates=dates, symbols=symbols, values=values)
        self.assertEqual(panel.values.shape, (len(dates), len(symbols)))

    def test_values_can_be_indexed_by_time_and_symbol(self) -> None:
        # Helper: values[t, i] should correspond to the t-th date and i-th symbol.
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        symbols = ["AAA", "BBB"]
        values = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)

        panel = AlignedPanel(dates=dates, symbols=symbols, values=values)
        self.assertAlmostEqual(panel.values[0, 1], 20.0)
        self.assertAlmostEqual(panel.values[1, 0], 30.0)
