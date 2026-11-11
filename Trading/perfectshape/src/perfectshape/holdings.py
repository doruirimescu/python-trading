"""ETF holdings as a universe: ``universe.lists: ["etf:XLK"]`` (with ``universe.limit: 20`` = top 20 by weight).

Select Sector SPDR holdings come from State Street's daily holdings file (xlsx, every constituent with its
weight), cached once per day under ``data_cache/holdings/``. Rows that are not stocks (cash, money-market,
futures) are dropped, and a second share class of the same company (GOOG next to GOOGL) is dropped too: a
ratio of two classes of one company is not a relationship between two businesses.
"""

from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SECTOR_ETFS: dict[str, str] = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}

SSGA_URL = ("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/"
            "holdings-daily-us-en-{etf}.xlsx")
CACHE_DIR = Path(os.environ.get("PERFECTSHAPE_HOLDINGS_CACHE",
                                Path(__file__).resolve().parents[2] / "data_cache" / "holdings"))

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,7}$")
_NOT_STOCK = re.compile(r"MONEY MARKET|CASH|FUTURE|FUT\b|U\.?S\.? DOLLAR|TREASURY", re.I)
# index futures the funds hold for cash equitisation: "Xab Materials Dec26" / ticker IXDZ6
_FUTURE_NAME = re.compile(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d{2}\s*$", re.I)
_FUTURE_TICKER = re.compile(r"^[A-Z]{3,4}[FGHJKMNQUVXZ]\d$")
_SHARE_CLASS = re.compile(r"\s+(CL(ASS)?\.?\s*[A-Z]|SERIES\s+[A-Z])\b.*$", re.I)


@dataclass
class Holding:
    ticker: str
    name: str
    weight: float          # percent of the fund


def holdings(etf: str, *, today: date | None = None, refresh: bool = False) -> list[Holding]:
    """Constituents of ``etf``, largest weight first."""
    etf = etf.upper()
    today = today or date.today()
    path = CACHE_DIR / f"{etf}_{today.isoformat()}.json"
    if path.exists() and not refresh:
        return [Holding(**h) for h in json.loads(path.read_text(encoding="utf-8"))]
    rows = parse_ssga_xlsx(_download(etf))
    if not rows:
        raise ValueError(f"no holdings parsed for {etf}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([h.__dict__ for h in rows], indent=1), encoding="utf-8")
    return rows


def _download(etf: str) -> bytes:
    import requests

    if etf not in SECTOR_ETFS:
        raise KeyError(f"holdings are available for the Select Sector SPDRs: {', '.join(SECTOR_ETFS)}")
    r = requests.get(SSGA_URL.format(etf=etf.lower()), timeout=30,
                     headers={"User-Agent": "Mozilla/5.0 (perfectshape holdings fetcher)"})
    r.raise_for_status()
    return r.content


def parse_ssga_xlsx(content: bytes) -> list[Holding]:
    import pandas as pd

    raw = pd.read_excel(io.BytesIO(content), header=None)
    head = next(i for i, row in raw.iterrows()
                if {"Ticker", "Weight"} <= {str(v).strip() for v in row.values})
    df = raw.iloc[head + 1:].copy()
    df.columns = [str(v).strip() for v in raw.iloc[head].values]
    out: list[Holding] = []
    seen_names: set[str] = set()
    for _, row in df.iterrows():
        t, name = str(row.get("Ticker", "")).strip().upper(), str(row.get("Name", "")).strip()
        try:
            w = float(row.get("Weight"))
        except (TypeError, ValueError):
            continue
        if (not _TICKER.match(t) or not (w > 0) or _NOT_STOCK.search(name) or _FUTURE_NAME.search(name)
                or _FUTURE_TICKER.match(t)):
            continue
        company = _SHARE_CLASS.sub("", name).upper()
        if company in seen_names:
            continue
        seen_names.add(company)
        from perfectshape.universe import normalize_ticker
        out.append(Holding(normalize_ticker(t), name.title(), w))
    out.sort(key=lambda h: -h.weight)
    return out
