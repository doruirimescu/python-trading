from mrscore.io.yfinance_loader import YFinanceLoader, YFinanceLoadRequest
from mrscore.io.history import OHLC
from mrscore.app.universe_runner import run_ratio_universe

def main():
    tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA"]

    loader = YFinanceLoader()
    histories = loader.load(
        YFinanceLoadRequest(tickers=tickers, period="5y", interval="1d", auto_adjust=True)
    )

    res = run_ratio_universe(
        config_path="config.yaml",
        histories=histories,
        symbols=tickers,
        field=OHLC.CLOSE,
        k_num=3,
        k_den=3,
        max_jobs=10_000,
    )

    print(res)

if __name__ == "__main__":
    main()
