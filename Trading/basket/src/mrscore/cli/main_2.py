# main_2.py
from __future__ import annotations

import numpy as np

from mrscore.config.loader import load_config
from mrscore.core.ratio_universe import RatioUniverse, RatioJob
from mrscore.core.ranking import TopKRanker
from mrscore.io.adapters import build_price_panel
from mrscore.io.history import OHLC
from mrscore.io.ratio import RatioSpec, build_equal_weight_basket
from mrscore.io.yfinance_loader import YFinanceLoader, YFinanceLoadRequest
from mrscore.utils.logging import get_logger
from mrscore.viz import plot_ratio_jobs, plot_equity_curve

# Pick ONE of these imports depending on where you placed it:
# from mrscore.app.composition_root import build_app
from mrscore.app.composition_root import build_app


logger = get_logger(__name__)


def _compute_returns_inplace(
    *,
    prices: np.ndarray,
    returns_out: np.ndarray,
    tmp_out: np.ndarray | None,
    mode: str,
) -> np.ndarray:
    """
    Compute returns from prices into a preallocated output array.

    prices: shape (T,)
    returns_out: shape (T-1,)
    tmp_out: shape (T-1,) if mode=="log", else None
    mode: "log" | "simple"
    """
    if mode == "simple":
        np.divide(prices[1:], prices[:-1], out=returns_out)
        returns_out -= 1.0
        return returns_out

    if mode == "log":
        if tmp_out is None:
            raise ValueError("tmp_out is required for log returns")
        np.log(prices[1:], out=returns_out)   # log(p_t)
        np.log(prices[:-1], out=tmp_out)      # log(p_{t-1})
        returns_out -= tmp_out
        return returns_out

    raise ValueError(f"Invalid returns mode: {mode}")


def _select_top_k_jobs(
    *,
    ru: RatioUniverse,
    engine,  # MeanReversionEngine, typed loosely to avoid import cycles
    returns_mode: str,
    vol_unit: str,
    k_num: int,
    k_den: int,
    max_jobs: int | None,
    top_k: int,
) -> tuple[list[RatioJob], dict[RatioJob, float]]:
    """
    Streaming top-k selection by REAL engine score.

    - avoids storing all scores
    - O(J log K)
    - uses preallocated buffers for ratio + returns
    """
    ranker = TopKRanker(top_k)

    # Reuse a buffer to avoid allocating (T,) arrays for every ratio
    T = ru._X.shape[0]  # if you prefer, add a public property on RatioUniverse
    price_buf = np.empty(T, dtype=np.float64)

    # Returns buffers (only if needed)
    ret_buf = None
    tmp_buf = None
    if vol_unit == "returns":
        if returns_mode == "none":
            raise ValueError("volatility_unit is 'returns' but returns_mode is 'none'")
        ret_buf = np.empty(T - 1, dtype=np.float64)
        if returns_mode == "log":
            tmp_buf = np.empty(T - 1, dtype=np.float64)

    # Track scores for plotting
    scores: dict[RatioJob, float] = {}

    for job in ru.iter_ratio_jobs(k_num=k_num, k_den=k_den, max_jobs=max_jobs):
        ru.compute_ratio_series_into(price_buf, job)

        # Prepare returns if required by engine/vol unit
        returns = None
        if vol_unit == "returns":
            assert ret_buf is not None
            returns = _compute_returns_inplace(
                prices=price_buf,
                returns_out=ret_buf,
                tmp_out=tmp_buf,
                mode=returns_mode,
            )

        result = engine.run(prices=price_buf, returns=returns, dates=ru.dates)
        score = float(result.score)

        # Skip NaN scores (e.g., record_empty_scores=False with 0 events)
        if not np.isfinite(score):
            continue

        ranker.consider(job=job, score=score)
        # store score for this job if it makes it into the heap; to keep it simple, store always
        scores[job] = score

    top = ranker.items_sorted(descending=True)

    if top:
        logger.info("Top-1 score=%f job=%s", top[0].score, top[0].job)
        logger.info("Top-%d cutoff score=%f", len(top), top[-1].score)

    jobs = [r.job for r in top]
    # Only return scores for the selected top jobs (keeps plot legend clean)
    top_scores = {r.job: r.score for r in top}
    return jobs, top_scores


def _job_to_ratio_spec(ru: RatioUniverse, job: RatioJob) -> tuple[RatioSpec, str]:
    lib_num = ru.get_basket_library(job.k_num)
    lib_den = lib_num if job.k_num == job.k_den else ru.get_basket_library(job.k_den)

    num_idx = lib_num.baskets[job.num_id]
    den_idx = lib_den.baskets[job.den_id]

    num_syms, den_syms = ru.job_to_symbols(job)
    job_id = f"{'+'.join(num_syms)} / {'+'.join(den_syms)}"

    spec = RatioSpec(
        numerator=build_equal_weight_basket(num_idx),
        denominator=build_equal_weight_basket(den_idx),
        eps=1e-12,
    )
    return spec, job_id


def main():
    cfg = load_config("config.yaml")  # loader returns RootConfig in your project
    tickers = cfg.data.tickers
    period = cfg.data.period
    interval = cfg.data.interval

    # Build composed application (engine + components)
    app = build_app(cfg)
    engine = app.engine

    # Determine returns_mode and volatility_unit for correct engine invocation
    returns_mode = cfg.data.returns_mode  # "log" | "simple" | "none"
    vol_unit = cfg.volatility_estimator.params.volatility_unit  # "returns" | "price"

    logger.info("Starting main_2: tickers=%s", tickers)
    loader = YFinanceLoader()
    histories = loader.load(
        YFinanceLoadRequest(tickers=tickers, period=period, interval=interval, auto_adjust=True)
    )
    logger.info("Loaded histories: %d tickers", len(histories))

    panel_raw = build_price_panel(
        histories=histories,
        symbols=tickers,
        field=OHLC.CLOSE,
        align="intersection",
        normalize_by_first=False,
    )
    ru = RatioUniverse(panel=panel_raw, normalize_by_first=True, eps=1e-12)

    top_k = cfg.visualization.top_k or 10
    ratio_cfg = cfg.ratio_universe

    logger.info(
        "Ranking top %d ratio jobs by engine score (k_num=%d k_den=%d max_jobs=%s returns_mode=%s vol_unit=%s)",
        top_k,
        ratio_cfg.k_num,
        ratio_cfg.k_den,
        ratio_cfg.max_jobs,
        returns_mode,
        vol_unit,
    )

    jobs, scores = _select_top_k_jobs(
        ru=ru,
        engine=engine,
        returns_mode=returns_mode,
        vol_unit=vol_unit,
        k_num=ratio_cfg.k_num,
        k_den=ratio_cfg.k_den,
        max_jobs=ratio_cfg.max_jobs,
        top_k=top_k,
    )

    trades_by_job = None
    if app.backtester is not None:
        bt_results = []
        trades_by_job = {}
        for job in jobs:
            spec, job_id = _job_to_ratio_spec(ru, job)
            result = app.backtester.run_one(panel=panel_raw, ratio_spec=spec, job_id=job_id)
            bt_results.append(result)
            trades_by_job[job] = result.trades or []
            logger.info(
                "Backtest %s: return=%.2f%% trades=%d",
                job_id,
                result.total_return * 100.0,
                len(result.trades or []),
            )
            if result.equity_curve:
                plot_equity_curve(result=result, title=f"Equity Curve | {job_id}", show=True)

    plot_ratio_jobs(
        ru=ru,
        jobs=jobs,
        config=cfg.visualization,
        scores=scores,
        mean_config=cfg.mean_estimator,
        trades_by_job=trades_by_job,
        show=True,
    )


if __name__ == "__main__":
    main()
