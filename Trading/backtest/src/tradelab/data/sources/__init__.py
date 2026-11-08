from __future__ import annotations

from .databento_src import CostLimitExceeded, DatabentoSource
from .files import PRESETS, CsvSource, ParquetSource
from .synthetic import SyntheticSource
from .yfinance_src import YFinanceSource

SOURCES = {
    "yfinance": YFinanceSource,
    "csv": CsvSource,
    "parquet": ParquetSource,
    "databento": DatabentoSource,
    "synthetic": SyntheticSource,
}


def get_source(name: str, **kw):
    if name not in SOURCES:
        raise KeyError(f"unknown source {name!r}; available: {sorted(SOURCES)}")
    return SOURCES[name](**kw)


def list_sources() -> list[str]:
    return sorted(SOURCES)


__all__ = ["SOURCES", "PRESETS", "get_source", "list_sources", "CostLimitExceeded", "DatabentoSource", "SyntheticSource"]
