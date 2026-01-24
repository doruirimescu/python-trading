from __future__ import annotations

from mrscore.app.universe_runner import run_ratio_universe
from mrscore.io.history import OHLC, History

# Placeholder: you will replace this with your real loader that returns Dict[str, History]
def load_histories_for_symbols(symbols) -> dict[str, History]:
    raise NotImplementedError


def main() -> None:
    config_path = "config.yaml"

    symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "XOM"]
    histories = load_histories_for_symbols(symbols)

    def on_result(job, score):
        # In reality: persist to parquet, DB, or accumulate top-N
        # You can also decode job -> symbols via ru.job_to_symbols(job) if you expose ru
        print(score)

    res = run_ratio_universe(
        config_path=config_path,
        histories=histories,
        symbols=symbols,
        field=OHLC.CLOSE,
        k_num=3,
        k_den=3,
        disallow_overlap=True,
        unordered_if_equal_k=True,
        max_jobs=1000,
        on_result=on_result,
    )

    print(f"Processed jobs: {res.processed_jobs}")


if __name__ == "__main__":
    main()
