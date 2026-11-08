"""Instrument universes.

A universe is a list of yfinance tickers with optional metadata (name, sector). Lists live as files in
``universes/`` (or anywhere, by path), so adding a market means dropping in a file:

* ``.csv``  - header row with a ``ticker`` column (optional ``name``, ``sector``)
* ``.txt``  - one ticker per line, ``#`` comments allowed (``TICKER  # name`` also fine)
* ``.json`` - list of tickers, or ``{ticker: name | [ticker, name, ...]}`` (the Trading/symbols format)
* ``.yaml`` - list of tickers or ``{tickers: [...]}``

Built-in fetchers (``perfectshape universe refresh <name>``) regenerate a list from its public source.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_DIR = Path(os.environ.get("PERFECTSHAPE_UNIVERSES", PROJECT_ROOT / "universes"))
_SUFFIXES = (".csv", ".txt", ".json", ".yaml", ".yml")


@dataclass
class Universe:
    tickers: list[str]
    meta: dict[str, dict[str, str]] = field(default_factory=dict)  # ticker -> {"name", "sector"}

    def name(self, t: str) -> str:
        return self.meta.get(t, {}).get("name", "")

    def sector(self, t: str) -> str:
        return self.meta.get(t, {}).get("sector", "")


def normalize_ticker(t: str) -> str:
    """Wikipedia/exchange style -> yfinance style (BRK.B -> BRK-B). Suffixed tickers (NESN.SW) are kept."""
    t = t.strip().upper()
    if "." in t:
        base, suffix = t.rsplit(".", 1)
        if len(suffix) == 1:  # share class, not an exchange suffix
            return f"{base}-{suffix}"
    return t


def resolve_list_path(name_or_path: str) -> Path:
    p = Path(name_or_path).expanduser()
    if p.suffix and p.exists():
        return p
    for suf in _SUFFIXES:
        cand = UNIVERSE_DIR / f"{name_or_path}{suf}"
        if cand.exists():
            return cand
    available = sorted(x.stem for x in UNIVERSE_DIR.glob("*") if x.suffix in _SUFFIXES)
    raise FileNotFoundError(f"universe list {name_or_path!r} not found; available: {available}")


def read_list(path: Path) -> Universe:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, dict[str, str]] = {}
    tickers: list[str] = []

    def add(t: str, name: str = "", sector: str = "") -> None:
        t = normalize_ticker(t)
        if not t or t in meta:
            return
        tickers.append(t)
        meta[t] = {"name": name, "sector": sector}

    suf = path.suffix.lower()
    if suf == ".csv":
        for row in csv.DictReader(io.StringIO(text)):
            add(row["ticker"], row.get("name", "") or "", row.get("sector", "") or "")
    elif suf == ".txt":
        for line in text.splitlines():
            body, _, comment = line.partition("#")
            if body.strip():
                add(body.split()[0], comment.strip())
    elif suf == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            for k, v in data.items():
                name = v[1] if isinstance(v, list) and len(v) > 1 else (v if isinstance(v, str) else "")
                add(k, name)
        else:
            for t in data:
                add(str(t))
    else:
        data = yaml.safe_load(text)
        items = data.get("tickers", []) if isinstance(data, dict) else data
        for t in items or []:
            add(str(t))
    return Universe(tickers, meta)


def build_universe(lists: Iterable[str], tickers: Iterable[str] = (), exclude: Iterable[str] = (),
                   limit: int | None = None) -> Universe:
    out = Universe([], {})
    for name in lists:
        u = read_list(resolve_list_path(name))
        for t in u.tickers:
            if t not in out.meta:
                out.tickers.append(t)
                out.meta[t] = u.meta[t]
    for t in tickers:
        t = normalize_ticker(t)
        if t not in out.meta:
            out.tickers.append(t)
            out.meta[t] = {"name": "", "sector": ""}
    excl = {normalize_ticker(t) for t in exclude}
    out.tickers = [t for t in out.tickers if t not in excl]
    if limit:
        out.tickers = out.tickers[:limit]
    out.meta = {t: out.meta[t] for t in out.tickers}
    return out


# ---------------------------------------------------------------- fetchers (network)

def _fetch_sp500() -> list[dict[str, str]]:
    import pandas as pd
    import requests

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    r = requests.get(url, headers={"User-Agent": "perfectshape universe fetcher"}, timeout=30)
    r.raise_for_status()
    table = pd.read_html(io.StringIO(r.text))[0]
    return [
        {"ticker": normalize_ticker(str(s)), "name": str(n), "sector": str(g)}
        for s, n, g in zip(table["Symbol"], table["Security"], table["GICS Sector"])
    ]


FETCHERS: dict[str, Callable[[], list[dict[str, str]]]] = {
    "sp500": _fetch_sp500,
}


def refresh(name: str) -> Path:
    if name not in FETCHERS:
        raise KeyError(f"no fetcher for {name!r}; known: {sorted(FETCHERS)}")
    rows = FETCHERS[name]()
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    path = UNIVERSE_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "name", "sector"])
        w.writeheader()
        w.writerows(rows)
    return path
