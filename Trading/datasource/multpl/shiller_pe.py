#!/usr/bin/env python3
"""
Fetch the current Shiller (CAPE) P/E ratio for the S&P 500.

Primary source: https://www.multpl.com/shiller-pe/table/by-month
- We read the first row of the first table (latest month) and extract the number.
Fallback: parse the same page with BeautifulSoup if pandas.read_html isn't available.

Usage:
    python get_shiller_pe.py
"""

import re
import sys
from typing import Tuple

import requests

URL = "https://www.multpl.com/shiller-pe/table/by-month"
HEADERS = {
    # A friendly UA makes some sites happier about returning full HTML.
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

import re

def extract_value_from_text(row_text: str) -> float:
    # Get all number-like tokens, including "40.21" and "40,21"
    tokens = re.findall(r"-?\d+(?:[.,]\d+)?", row_text)
    if not tokens:
        raise ValueError("No numeric tokens found.")

    # Normalize commas to dots
    tokens = [t.replace(",", ".") for t in tokens]

    # Prefer the first token that contains a decimal part
    for t in tokens:
        if "." in t:
            return float(t)

    # Fallback: last numeric token (often the value column)
    return float(tokens[-1])

def parse_with_pandas(html: str):
    import pandas as pd
    tables = pd.read_html(html)
    df = next((t for t in tables if not t.empty), None)
    row0 = df.iloc[0]
    row_text = " ".join(map(str, row0.tolist()))
    date_str = str(row0.iloc[0])
    value = extract_value_from_text(row_text)
    return date_str, value

def parse_with_bs4(html: str):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    first_row = table.find("tr")
    if first_row and first_row.find_all("th"):
        first_row = first_row.find_next_sibling("tr")
    cells = [c.get_text(strip=True) for c in first_row.find_all(["td", "th"])]
    row_text = " ".join(cells)
    date_str = cells[0] if cells else "Latest"
    value = extract_value_from_text(row_text)
    return date_str, value


def get_shiller_pe() -> Tuple[str, float]:
    html = fetch_html(URL)
    # Try pandas first (most reliable for tables), then fall back.
    try:
        return parse_with_pandas(html)
    except Exception:
        try:
            return parse_with_bs4(html)
        except Exception as e2:
            raise RuntimeError(f"Failed to parse CAPE value: {e2}")

if __name__ == "__main__":
    try:
        date_str, value = get_shiller_pe()
        print(f"Shiller (CAPE) P/E — {value:.2f} ({date_str})")
        print(f"Source: {URL}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
