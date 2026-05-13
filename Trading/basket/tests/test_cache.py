import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from mrscore.core.ratio_universe import RatioUniverse
from mrscore.io.adapters import AlignedPanel, build_price_panel
from mrscore.io.cache import (
    compute_cache_key,
    load_panel_from_cache,
    load_ratio_jobs_from_cache,
    panel_cache_payload,
    ratio_jobs_cache_payload,
    store_panel_to_cache,
    store_ratio_jobs_to_cache,
)
from mrscore.io.history import History, OHLC


class TestCachePanel(unittest.TestCase):
    def test_panel_cache_round_trip(self) -> None:
        dates = np.array(["2024-01-01", "2024-01-02", "2024-01-03"], dtype="datetime64[D]")
        histories = {
            "AAA": History(symbol="AAA", dates=dates, close=np.array([1.0, 2.0, 3.0])),
            "BBB": History(symbol="BBB", dates=dates, close=np.array([4.0, 5.0, 6.0])),
        }

        panel = build_price_panel(
            histories=histories,
            symbols=["AAA", "BBB"],
            field=OHLC.CLOSE,
            align="intersection",
            normalize_by_first=False,
        )

        payload = panel_cache_payload(
            tickers=["AAA", "BBB"],
            period="5y",
            interval="1d",
            ending_date=date(2024, 1, 3),
            price_field="close",
            align="intersection",
            normalize_by_first=False,
            union_fill="none",
        )
        key = compute_cache_key(payload)

        with TemporaryDirectory() as tmp_dir:
            cache_root = Path(tmp_dir)
            store_panel_to_cache(cache_root, key, panel, payload)
            loaded = load_panel_from_cache(cache_root, key)

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(np.array_equal(loaded.dates, panel.dates))
        self.assertEqual(loaded.symbols, panel.symbols)
        self.assertTrue(np.allclose(loaded.values, panel.values))


class TestCacheRatioJobs(unittest.TestCase):
    def test_ratio_jobs_cache_round_trip(self) -> None:
        dates = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]")
        values = np.array(
            [
                [1.0, 2.0, 3.0, 4.0],
                [1.1, 2.2, 3.3, 4.4],
            ],
            dtype=np.float64,
        )
        panel = AlignedPanel(dates=dates, symbols=["A", "B", "C", "D"], values=values)
        ru = RatioUniverse(panel=panel, normalize_by_first=False, eps=1e-12)

        jobs = list(
            ru.iter_ratio_jobs(
                k_num=2,
                k_den=2,
                unordered_if_equal_k=True,
                disallow_overlap=False,
                max_jobs=5,
            )
        )

        payload = ratio_jobs_cache_payload(
            panel_key="panel-key",
            k_num=2,
            k_den=2,
            unordered_if_equal_k=True,
            disallow_overlap=False,
            max_jobs=5,
        )
        key = compute_cache_key(payload)

        with TemporaryDirectory() as tmp_dir:
            cache_root = Path(tmp_dir)
            store_ratio_jobs_to_cache(cache_root, key, ru=ru, jobs=jobs, payload=payload)

            ru_loaded = RatioUniverse(panel=panel, normalize_by_first=False, eps=1e-12)
            loaded_jobs = load_ratio_jobs_from_cache(cache_root, key, ru=ru_loaded)

        self.assertIsNotNone(loaded_jobs)
        assert loaded_jobs is not None
        self.assertEqual(loaded_jobs, jobs)
        self.assertIn(2, ru_loaded._basket_libs)
        self.assertEqual(ru_loaded._basket_libs[2].baskets.shape[1], 2)
