from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import hashlib
import json
import os

import numpy as np

from mrscore.core.ratio_universe import BasketLibrary, RatioJob, RatioUniverse
from mrscore.io.adapters import AlignedPanel
from mrscore.utils.logging import get_logger


logger = get_logger(__name__)


def panel_cache_payload(
    *,
    tickers: Sequence[str],
    period: str,
    interval: str,
    ending_date: Optional[date],
    price_field: str,
    align: str,
    normalize_by_first: bool,
    union_fill: str,
) -> dict[str, Any]:
    return {
        "v": 1,
        "tickers": list(tickers),
        "period": period,
        "interval": interval,
        "ending_date": ending_date.isoformat() if ending_date else None,
        "price_field": price_field,
        "align": align,
        "normalize_by_first": normalize_by_first,
        "union_fill": union_fill,
    }


def ratio_jobs_cache_payload(
    *,
    panel_key: str,
    k_num: int,
    k_den: int,
    unordered_if_equal_k: bool,
    disallow_overlap: bool,
    max_jobs: Optional[int],
) -> dict[str, Any]:
    return {
        "v": 1,
        "panel_key": panel_key,
        "k_num": k_num,
        "k_den": k_den,
        "unordered_if_equal_k": unordered_if_equal_k,
        "disallow_overlap": disallow_overlap,
        "max_jobs": max_jobs,
    }


def compute_cache_key(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_panel_from_cache(cache_root: Path, key: str) -> Optional[AlignedPanel]:
    path = _panel_dir(cache_root, key) / "panel.npz"
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            dates = np.asarray(data["dates"], dtype="datetime64[D]")
            symbols = [_as_text(s) for s in data["symbols"]]
            values = np.asarray(data["values"], dtype=np.float64)
            return AlignedPanel(dates=dates, symbols=symbols, values=values)
    except Exception:
        logger.warning("Failed to read panel cache: %s", path, exc_info=True)
        return None


def store_panel_to_cache(
    cache_root: Path,
    key: str,
    panel: AlignedPanel,
    payload: Mapping[str, Any],
) -> None:
    cache_dir = _panel_dir(cache_root, key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_dir / "panel.tmp.npz"
    final_path = cache_dir / "panel.npz"
    try:
        np.savez_compressed(
            tmp_path,
            dates=np.asarray(panel.dates, dtype="datetime64[D]"),
            symbols=np.asarray(panel.symbols),
            values=np.asarray(panel.values, dtype=np.float64),
        )
        os.replace(tmp_path, final_path)
        _write_manifest(cache_dir, payload)
    except Exception:
        logger.warning("Failed to write panel cache: %s", final_path, exc_info=True)


def load_ratio_jobs_from_cache(
    cache_root: Path,
    key: str,
    *,
    ru: RatioUniverse,
) -> Optional[list[RatioJob]]:
    path = _ratio_dir(cache_root, key) / "ratiojobs.npz"
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            k_num = int(data["k_num"][0])
            k_den = int(data["k_den"][0])
            baskets_num = np.asarray(data["baskets_num"], dtype=np.int32)
            baskets_den = np.asarray(data["baskets_den"], dtype=np.int32)
            num_ids = np.asarray(data["num_ids"], dtype=np.int32)
            den_ids = np.asarray(data["den_ids"], dtype=np.int32)

        _set_basket_library(ru, k_num, baskets_num)
        if k_den != k_num:
            _set_basket_library(ru, k_den, baskets_den)
        else:
            _set_basket_library(ru, k_den, baskets_num)

        jobs = [
            RatioJob(k_num=k_num, k_den=k_den, num_id=int(n), den_id=int(d))
            for n, d in zip(num_ids, den_ids)
        ]
        return jobs
    except Exception:
        logger.warning("Failed to read ratiojobs cache: %s", path, exc_info=True)
        return None


def store_ratio_jobs_to_cache(
    cache_root: Path,
    key: str,
    *,
    ru: RatioUniverse,
    jobs: Sequence[RatioJob],
    payload: Mapping[str, Any],
) -> None:
    if not jobs:
        return
    k_num = jobs[0].k_num
    k_den = jobs[0].k_den
    lib_num = ru.get_basket_library(k_num)
    lib_den = lib_num if k_num == k_den else ru.get_basket_library(k_den)

    cache_dir = _ratio_dir(cache_root, key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_dir / "ratiojobs.tmp.npz"
    final_path = cache_dir / "ratiojobs.npz"
    try:
        np.savez_compressed(
            tmp_path,
            k_num=np.array([k_num], dtype=np.int32),
            k_den=np.array([k_den], dtype=np.int32),
            baskets_num=np.asarray(lib_num.baskets, dtype=np.int32),
            baskets_den=np.asarray(lib_den.baskets, dtype=np.int32),
            num_ids=np.asarray([j.num_id for j in jobs], dtype=np.int32),
            den_ids=np.asarray([j.den_id for j in jobs], dtype=np.int32),
        )
        os.replace(tmp_path, final_path)
        _write_manifest(cache_dir, payload)
    except Exception:
        logger.warning("Failed to write ratiojobs cache: %s", final_path, exc_info=True)


def _panel_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "panels" / key


def _ratio_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "ratiojobs" / key


def _set_basket_library(ru: RatioUniverse, k: int, baskets: np.ndarray) -> None:
    lib = BasketLibrary(k=k, baskets=np.asarray(baskets, dtype=np.int32))
    ru._basket_libs[k] = lib


def _write_manifest(cache_dir: Path, payload: Mapping[str, Any]) -> None:
    tmp_path = cache_dir / "manifest.tmp.json"
    final_path = cache_dir / "manifest.json"
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, indent=2, default=_json_default)
        os.replace(tmp_path, final_path)
    except Exception:
        logger.warning("Failed to write cache manifest: %s", final_path, exc_info=True)


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
