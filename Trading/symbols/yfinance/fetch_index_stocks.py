"""
Fetch S&P 500 and FTSE All-World index constituent tickers.

  S&P 500     — Wikipedia constituent table (stable, maintained by community)
  FTSE AW     — Vanguard VT ETF portfolio API (tracks FTSE Global All Cap Index,
                which is FTSE All-World + small-cap; ~10 000 stocks)

Output format matches all_stocks.json:
    { "AAPL": ["AAPL", "Apple Inc.", "https://finance.yahoo.com/quote/AAPL/"] }

Usage:
    python fetch_index_stocks.py            # both indices
    python fetch_index_stocks.py --sp500
    python fetch_index_stocks.py --ftse
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import requests

SCRIPT_DIR = Path(__file__).parent

SP500_FILE = SCRIPT_DIR / "sp500_stocks.json"
FTSE_AW_FILE = SCRIPT_DIR / "ftse_allworld_stocks.json"

SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Vanguard VT ETF — tracks FTSE Global All Cap (= FTSE All-World + small-cap)
VT_API_URL = (
    "https://investor.vanguard.com/investment-products/etfs/profile/api/"
    "VT/portfolio-holding/stock"
)
VT_PAGE_SIZE = 500

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Python/requests)"}

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ISIN country code → yfinance exchange suffix.
# Countries absent from this map are assumed to already be in yfinance format (US)
# or have no reliable single exchange.
_ISIN_SUFFIX: dict[str, str] = {
    "AT": ".VI",
    "AU": ".AX",
    "BE": ".BR",
    "BR": ".SA",
    "CA": ".TO",
    "CH": ".SW",
    "CL": ".SN",
    "DE": ".DE",
    "DK": ".CO",
    "EG": ".CA",
    "ES": ".MC",
    "FI": ".HE",
    "FR": ".PA",
    "GB": ".L",
    "GR": ".AT",
    "HK": ".HK",   # also zero-padded to 4 digits; handled in _to_yf_symbol
    "ID": ".JK",
    "IE": ".I",
    "IL": ".TA",
    "IN": ".NS",
    "IT": ".MI",
    "JP": ".T",
    "KW": ".KW",
    "MX": ".MX",
    "MY": ".KL",
    "NL": ".AS",
    "NO": ".OL",
    "NZ": ".NZ",
    "PH": ".PS",
    "PL": ".WA",
    "PT": ".LS",
    "QA": ".QA",
    "SA": ".SR",
    "SE": ".ST",
    "SG": ".SI",
    "TH": ".BK",   # -F/-R/-W exchange suffixes stripped; handled in _to_yf_symbol
    "TR": ".IS",   # -E exchange suffix stripped; handled in _to_yf_symbol
    "TW": ".TW",
    "ZA": ".JO",
}

# Vanguard-specific trailing qualifiers that are NOT part of the yfinance ticker
_TH_STRIP = ("-F", "-R", "-W", "-P")   # Thai foreign/NVDR/warrant shares


def _to_yf_symbol(ticker: str, isin: str) -> str:
    """Convert a Vanguard-format ticker + ISIN to the correct yfinance symbol."""
    if not ticker:
        return ticker

    country = isin[:2] if isin and len(isin) >= 2 else ""

    if not country or country == "US":
        return ticker

    t = ticker

    # Strip exchange-qualifier suffixes that Vanguard appends but yfinance doesn't use
    if country == "TH":
        for sfx in _TH_STRIP:
            if t.endswith(sfx):
                t = t[: -len(sfx)]
                break
    elif country == "TR" and t.endswith("-E"):
        t = t[:-2]

    # Country-specific suffix logic
    if country == "CN":
        # Shanghai tickers start with 6; everything else is Shenzhen
        suffix = ".SS" if t and t[0] == "6" else ".SZ"
    elif country == "KR":
        # ISIN position 2: '7' = KOSPI (.KS), '8' = KOSDAQ (.KQ)
        suffix = ".KS" if len(isin) > 2 and isin[2] == "7" else ".KQ"
    elif country in ("HK", "KY") and t.isdigit():
        # HK-listed: direct HK ISIN, or Cayman-registered Chinese companies (KY ISIN)
        # KY + alphabetic ticker = US-listed ADR → handled below by the empty suffix
        t = t.zfill(4)   # '700' → '0700'
        suffix = ".HK"
    else:
        suffix = _ISIN_SUFFIX.get(country, "")

    return f"{t}{suffix}" if suffix else t


def fetch_sp500() -> dict[str, list]:
    """Scrape current S&P 500 constituents from Wikipedia."""
    print("Fetching S&P 500 from Wikipedia ...")
    df = pd.read_html(SP500_WIKI_URL, attrs={"id": "constituents"})[0]
    stocks = {}
    for _, row in df.iterrows():
        symbol = str(row["Symbol"]).strip().replace(".", "-")   # BRK.B → BRK-B
        name = str(row["Security"])
        stocks[symbol] = [symbol, name, f"https://finance.yahoo.com/quote/{symbol}/"]
    print(f"  {len(stocks)} tickers")
    return dict(sorted(stocks.items()))


def fetch_ftse_all_world() -> dict[str, list]:
    """Fetch FTSE All-World constituents via Vanguard's VT ETF portfolio API.

    VT tracks the FTSE Global All Cap Index (FTSE All-World + small-cap).
    ISINs from the API are used to derive the correct yfinance exchange suffix
    for each stock (e.g. 600020 → 600020.SS, 7203 → 7203.T).
    """
    print("Fetching FTSE All-World (Vanguard VT portfolio API) ...")
    stocks = {}
    start = 1
    total = None

    while True:
        resp = requests.get(
            VT_API_URL,
            params={"start": start, "count": VT_PAGE_SIZE},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if total is None:
            total = data.get("size", "?")

        for entity in data.get("fund", {}).get("entity", []):
            raw_ticker = str(entity.get("ticker", "")).strip()
            isin = str(entity.get("isin", "")).strip()
            name = str(entity.get("longName", "") or entity.get("shortName", "")).strip()
            if not raw_ticker or raw_ticker == "nan":
                continue
            symbol = _to_yf_symbol(raw_ticker, isin)
            stocks[symbol] = [symbol, name, f"https://finance.yahoo.com/quote/{symbol}/"]

        fetched = start + VT_PAGE_SIZE - 1
        print(f"  {min(fetched, total if isinstance(total, int) else fetched)}/{total}")

        if "next" not in data:
            break
        start += VT_PAGE_SIZE

    print(f"  {len(stocks)} unique tickers")
    return dict(sorted(stocks.items()))


def _save(stocks: dict, path: Path) -> None:
    with open(path, "w") as f:
        json.dump(stocks, f, indent=4)
    print(f"Saved → {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sp500", action="store_true", help="Fetch S&P 500 only")
    parser.add_argument("--ftse", action="store_true", help="Fetch FTSE All-World only")
    args = parser.parse_args()
    run_all = not args.sp500 and not args.ftse

    if args.sp500 or run_all:
        _save(fetch_sp500(), SP500_FILE)

    if args.ftse or run_all:
        _save(fetch_ftse_all_world(), FTSE_AW_FILE)
