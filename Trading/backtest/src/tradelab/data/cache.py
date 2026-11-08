"""Parquet cache keyed by sha256 of the request payload."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from ..util.hashing import stable_hash

CACHE_VERSION = 1


def project_root() -> Path:
    p = Path(__file__).resolve().parents[3]
    return p if (p / "pyproject.toml").exists() else Path.cwd()


def cache_key(source: str, symbol: str, start, end, freq: str, adjust: bool, session: str, **extra) -> str:
    payload = {"v": CACHE_VERSION, "source": source, "symbol": symbol, "start": start, "end": end,
               "freq": freq, "adjust": adjust, "session": session, **extra}
    return stable_hash(payload)


def cache_path(source: str, key: str, root: Path | None = None) -> Path:
    return (root or project_root() / "data_cache") / source / f"{key}.parquet"


def load_or_fetch(source: str, key: str, fetch: Callable[[], pd.DataFrame], *, refresh: bool = False, root: Path | None = None) -> pd.DataFrame:
    p = cache_path(source, key, root)
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    df = fetch()
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    return df
