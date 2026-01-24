# main_2.py
from __future__ import annotations

import numpy as np

from mrscore.config.loader import load_config
from mrscore.core.ratio_universe import RatioUniverse, RatioJob
from mrscore.core.ranking import TopKRanker
from mrscore.io.adapters import build_price_panel
from mrscore.io.history import OHLC
from mrscore.io.yfinance_loader import YFinanceLoader, YFinanceLoadRequest
from mrscore.utils.logging import get_logger
from mrscore.viz import plot_ratio_jobs


logger = get_logger(__name__)


def _select_top_k_jobs(
    *,
    ru: RatioUniverse,
    k_num: int,
    k_den: int,
    max_jobs: int | None,
    top_k: int,
) -> tuple[list[RatioJob], dict[RatioJob, float]]:
    """
    Streaming top-k selection:
      - avoids storing all scores
      - O(J log K) instead of O(J log J)
    """
    ranker = TopKRanker(top_k)

    # Reuse a buffer to avoid allocating (T,) arrays for every ratio
    T = ru._X.shape[0]  # note: if you want to avoid using a private field, add ru.length property
    buf = np.empty(T, dtype=np.float64)

    for job in ru.iter_ratio_jobs(k_num=k_num, k_den=k_den, max_jobs=max_jobs):
        ru.compute_ratio_series_into(buf, job)

        # --- CURRENT "CRUDE" SCORE ---
        # Replace this with engine score later (ranker stays unchanged).
        score = float(np.nanmean(buf))

        ranker.consider(job=job, score=score)

    top = ranker.items_sorted(descending=True)

    # Helpful logging for quick sanity checks
    if top:
        logger.info("Top-1 score=%f job=%s", top[0].score, top[0].job)
        logger.info("Top-%d cutoff score=%f", len(top), top[-1].score)

    jobs = [r.job for r in top]
    scores = {r.job: r.score for r in top}
    return jobs, scores


def main():
    config = load_config("config.yaml")
    tickers = config.data.tickers
    period = config.data.period
    interval = config.data.interval

    logger.info("Starting main_2: tickers=%s", tickers)
    loader = YFinanceLoader()
    histories = loader.load(
        YFinanceLoadRequest(tickers=tickers, period=period, interval=interval, auto_adjust=True)
    )
    logger.info("Loaded histories: %d tickers", len(histories))

    panel = build_price_panel(
        histories=histories,
        symbols=tickers,
        field=OHLC.CLOSE,
        align="intersection",
        normalize_by_first=True,
    )
    ru = RatioUniverse(panel=panel, normalize_by_first=False, eps=1e-12)

    top_k = config.visualization.top_k or 10
    ratio_cfg = config.ratio_universe

    logger.info(
        "Selecting top %d ratio jobs for plotting (k_num=%d k_den=%d max_jobs=%s)",
        top_k,
        ratio_cfg.k_num,
        ratio_cfg.k_den,
        ratio_cfg.max_jobs,
    )

    jobs, scores = _select_top_k_jobs(
        ru=ru,
        k_num=ratio_cfg.k_num,
        k_den=ratio_cfg.k_den,
        max_jobs=ratio_cfg.max_jobs,
        top_k=top_k,
    )

    plot_ratio_jobs(
        ru=ru,
        jobs=jobs,
        config=config.visualization,
        scores=scores,
        mean_config=config.mean_estimator,
        show=True,
    )


if __name__ == "__main__":
    main()
