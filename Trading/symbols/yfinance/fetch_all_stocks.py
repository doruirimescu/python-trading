"""
Fetch all equity tickers from Yahoo Finance (via yfinance screener) for every
known exchange and store them enriched with company name:

    { "AAPL": ["AAPL", "Apple Inc.", "https://finance.yahoo.com/quote/AAPL/"], ... }

Progress is saved on interrupt so the script can be safely interrupted
and resumed — it skips exchanges that are already present in today's raw file.

Usage:
    python fetch_all_stocks.py
"""

import json
import logging
import time
from datetime import date
from pathlib import Path

import yfinance as yf
from stateful_data_processor.file_rw import JsonFileRW
from stateful_data_processor.parallel_processor import ParallelStatefulDataProcessor
from Trading.symbols.yfinance.constants import FILTERED_EXCHANGES

SCRIPT_DIR = Path(__file__).parent

RAW_FILE = SCRIPT_DIR / f"{date.today()}-all-equities.json"
OUTPUT_FILE = SCRIPT_DIR / "switzerland_stocks.json"


PAGE_SIZE = 250
REQUEST_DELAY = 0.5

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


class EquityFetcher(ParallelStatefulDataProcessor):
    def process_item(self, exchange: str, iteration_index: int):
        tickers = {}
        offset = 0
        query = yf.EquityQuery("eq", ["exchange", exchange])

        while True:
            try:
                result = yf.screen(query, size=PAGE_SIZE, offset=offset)
            except Exception as exc:
                print(f"  [{exchange}] request failed at offset {offset}: {exc}")
                break

            quotes = result.get("quotes", [])
            if not quotes:
                break

            for quote in quotes:
                symbol = quote.get("symbol")
                if symbol:
                    tickers[symbol] = quote

            total = result.get("total", 0)
            offset += len(quotes)
            print(f"  [{exchange}] {offset}/{total}")

            if offset >= total:
                break

            time.sleep(REQUEST_DELAY)

        self.data[exchange] = tickers
        time.sleep(REQUEST_DELAY)


def build_stocks_json(data: dict) -> dict:
    stocks = {}
    for exchange_tickers in data.values():
        for symbol, quote in exchange_tickers.items():
            name = quote.get("shortName") or quote.get("longName") or ""
            stocks[symbol] = [symbol, name, f"https://finance.yahoo.com/quote/{symbol}/"]
    return dict(sorted(stocks.items()))



if __name__ == "__main__":
    print(f"Raw snapshot  : {RAW_FILE}")
    print(f"Output        : {OUTPUT_FILE}\n")

    fetcher = EquityFetcher(JsonFileRW(str(RAW_FILE)), n_workers=4, logger=LOGGER)
    fetcher.run(FILTERED_EXCHANGES)

    total_raw = sum(len(v) for v in fetcher.data.values())
    print(f"\nBuilding {OUTPUT_FILE.name} from {total_raw} raw entries...")

    stocks = build_stocks_json(fetcher.data)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(stocks, f, indent=4)

    print(f"Done — {len(stocks)} unique tickers written to {OUTPUT_FILE.name}")
