"""
Fetch all equity tickers from Yahoo Finance (via yfinance screener) for every
known exchange and store them in the same format as stocks.json:

    { "AAPL": ["AAPL", "https://finance.yahoo.com/quote/AAPL/"], ... }

Progress is saved after each exchange so the script can be safely interrupted
and resumed — it skips exchanges that are already present in today's raw file.

Usage:
    python fetch_all_stocks.py
"""

import json
import time
from datetime import date
from pathlib import Path

import yfinance as yf

SCRIPT_DIR = Path(__file__).parent

# Dated raw snapshot (one file per run day; acts as a resume checkpoint)
RAW_FILE = SCRIPT_DIR / f"{date.today()}-all-equities.json"

# Final flat output in stocks.json format
OUTPUT_FILE = SCRIPT_DIR / "all_stocks.json"

# All exchanges observed in the historical all-equities dataset
EXCHANGES = [
    "AMS", "AQS", "ASE", "ASX", "ATH", "BER", "BRU", "BSE", "BTS", "BUD",
    "BUE", "BVB", "BVC", "CAI", "CCS", "CNQ", "CPH", "CXI", "DOH", "DUS",
    "EBS", "FKA", "FRA", "GER", "HAM", "HEL", "HKG", "ICE", "IOB", "ISE",
    "IST", "JKT", "JNB", "JPX", "KLS", "KOE", "KSC", "KUW", "LIS", "LIT",
    "LSE", "MCE", "MEX", "MIL", "MUN", "NCM", "NEO", "NGM", "NMS", "NSI",
    "NYQ", "NZE", "OEM", "OQB", "OQX", "OSL", "PAR", "PCX", "PHP", "PHS",
    "PNK", "PRA", "RIS", "SAO", "SAP", "SAU", "SES", "SET", "SGO", "SHH",
    "SHZ", "STO", "STU", "TAI", "TAL", "TLV", "TOR", "TWO", "VAN", "VIE",
    "WSE", "YHD",
]

PAGE_SIZE = 250
REQUEST_DELAY = 0.5  # seconds between paginated requests


def _fetch_exchange(exchange: str) -> dict:
    """Return {symbol: quote_dict} for every equity on the given exchange."""
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

    return tickers


def fetch_all_equities() -> dict:
    """
    Fetch all exchanges with per-exchange checkpointing.
    Returns {exchange: {symbol: quote_dict}}.
    """
    if RAW_FILE.exists():
        with open(RAW_FILE) as f:
            data = json.load(f)
        print(f"Resuming from {RAW_FILE.name} ({len(data)} exchanges already done)\n")
    else:
        data = {}

    for exchange in EXCHANGES:
        if exchange in data:
            print(f"[{exchange}] already fetched ({len(data[exchange])} tickers), skipping")
            continue

        print(f"Fetching [{exchange}]...")
        data[exchange] = _fetch_exchange(exchange)

        with open(RAW_FILE, "w") as f:
            json.dump(data, f, indent=4)

        print(f"[{exchange}] done — {len(data[exchange])} tickers saved\n")
        time.sleep(REQUEST_DELAY)

    return data


def build_stocks_json(data: dict) -> dict:
    """Flatten raw equities data into stocks.json format."""
    stocks = {}
    for exchange_tickers in data.values():
        for symbol in exchange_tickers:
            stocks[symbol] = [symbol, f"https://finance.yahoo.com/quote/{symbol}/"]
    return dict(sorted(stocks.items()))


if __name__ == "__main__":
    print(f"Raw snapshot  : {RAW_FILE}")
    print(f"Output        : {OUTPUT_FILE}\n")

    data = fetch_all_equities()

    total_raw = sum(len(v) for v in data.values())
    print(f"\nBuilding {OUTPUT_FILE.name} from {total_raw} raw entries...")

    stocks = build_stocks_json(data)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(stocks, f, indent=4)

    print(f"Done — {len(stocks)} unique tickers written to {OUTPUT_FILE.name}")
