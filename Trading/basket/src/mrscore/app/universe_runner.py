from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence

import numpy as np

from mrscore.config.loader import load_config
from mrscore.io.history import History, OHLC
from mrscore.io.adapters import build_price_panel
from mrscore.core.ratio_universe import RatioUniverse, RatioJob
from mrscore.core.ranking import TopKRanker, RankedJob
from mrscore.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class UniverseRunResult:
    processed_jobs: int
    stopped_early: bool
    top: Optional[list[RankedJob]] = None


def run_ratio_universe(
    *,
    config_path: str,
    histories: Dict[str, History],
    symbols: Sequence[str],
    field: OHLC = OHLC.CLOSE,
    k_num: int = 3,
    k_den: int = 3,
    disallow_overlap: bool = True,
    unordered_if_equal_k: bool = True,
    max_jobs: Optional[int] = None,
    on_result: Optional[Callable[[RatioJob, dict], None]] = None,
    top_k: Optional[int] = None,
) -> UniverseRunResult:
    runtime = load_config(config_path)

    panel = build_price_panel(
        histories=histories,
        symbols=symbols,
        field=field,
        align="intersection",
        normalize_by_first=True,
    )

    ru = RatioUniverse(panel=panel, normalize_by_first=False, eps=1e-12)

    T = panel.values.shape[0]
    ratio_buf = np.empty(T, dtype=np.float64)

    ranker = TopKRanker(top_k) if top_k is not None else None

    stopped_early = False

    def process(job: RatioJob, series_view: np.ndarray) -> bool:
        nonlocal stopped_early

        ratio_buf[:] = series_view

        # Placeholder score: replace with engine score when ready.
        score_value = float(np.nanmean(ratio_buf))
        score = {"job": job, "score": score_value}

        if ranker is not None:
            ranker.consider(job=job, score=score_value)

        if on_result is not None:
            on_result(job, score)

        return True

    processed = ru.scan(
        k_num=k_num,
        k_den=k_den,
        process=process,
        unordered_if_equal_k=unordered_if_equal_k,
        disallow_overlap=disallow_overlap,
        max_jobs=max_jobs,
        reuse_buffer=True,
    )

    return UniverseRunResult(
        processed_jobs=processed,
        stopped_early=stopped_early,
        top=(ranker.items_sorted(descending=True) if ranker is not None else None),
    )
