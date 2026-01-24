from mrscore.config.loader import load_config
from mrscore.core.ratio_universe import RatioUniverse, RatioJob
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
) -> list[RatioJob]:
    scored: list[tuple[float, RatioJob]] = []
    for job in ru.iter_ratio_jobs(k_num=k_num, k_den=k_den, max_jobs=max_jobs):
        series = ru.compute_ratio_series(job)
        score = float(series.mean())
        scored.append((score, job))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [job for _, job in scored[:top_k]]


def main():
    tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA"]

    logger.info("Starting main_2: tickers=%s", tickers)
    loader = YFinanceLoader()
    histories = loader.load(
        YFinanceLoadRequest(tickers=tickers, period="5y", interval="1d", auto_adjust=True)
    )

    logger.info("Loaded histories: %d tickers", len(histories))

    config = load_config("config.yaml")
    panel = build_price_panel(
        histories=histories,
        symbols=tickers,
        field=OHLC.CLOSE,
        align="intersection",
        normalize_by_first=True,
    )
    ru = RatioUniverse(panel=panel, normalize_by_first=False, eps=1e-12)

    top_k = config.visualization.top_k or 10
    logger.info("Selecting top %d ratio jobs for plotting", top_k)
    jobs = _select_top_k_jobs(ru=ru, k_num=3, k_den=3, max_jobs=10_000, top_k=top_k)

    plot_ratio_jobs(ru=ru, jobs=jobs, config=config.visualization, show=True)

if __name__ == "__main__":
    main()
