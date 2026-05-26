#!/usr/bin/env python3
"""Fetch S&P 500 market caps and write them to SP500_WEIGHTS_GENERATED_PATH."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import SP500_WEIGHTS_GENERATED_PATH, SP500_TODAY_PATH

# stock/yfinance/ shadows the real package; remove this directory from sys.path
_local = str(Path(__file__).parent)
_orig_path = sys.path[:]
sys.path = [p for p in sys.path if p != _local]
import yfinance as yf
sys.path = _orig_path


def fetch_market_caps(symbols: list) -> dict:
    import time
    print(f"Fetching market caps for {len(symbols)} tickers...", flush=True)
    batch = yf.Tickers(" ".join(symbols))
    caps = {}
    for i, sym in enumerate(symbols, 1):
        try:
            caps[sym] = batch.tickers[sym].fast_info.market_cap
        except Exception:
            caps[sym] = None
        time.sleep(0.15)
        if i % 50 == 0:
            print(f"  {i}/{len(symbols)}", flush=True)
    return caps


def load_symbols_from_file(path: Path) -> list:
    from summarize import resolve_and_load
    entries = resolve_and_load(path)
    return [e["symbol"] for e in entries]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch S&P 500 market caps")
    args = parser.parse_args()

    symbols = load_symbols_from_file(SP500_TODAY_PATH)
    caps = fetch_market_caps(symbols)

    out = Path(SP500_WEIGHTS_GENERATED_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(caps, f, indent=2)
    print(f"Saved {len(caps)} market caps to {out}")
