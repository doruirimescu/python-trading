"""Calendar time spans for annualisation."""
from __future__ import annotations

import pandas as pd


def years_span(index: pd.Index, periods_per_year: int = 252) -> float:
    """Length of a daily-return sample in YEARS, from the calendar span first..last date (inclusive) / 365.25.

    Counting rows / 252 instead is wrong whenever the sample has gaps (missing days, holidays beyond the
    252 convention, weekend-only crypto, partial years). Falls back to n / periods_per_year when the index is
    not a date index or has a single row.
    """
    n = len(index)
    if n == 0:
        return float("nan")
    if n > 1 and isinstance(index, pd.DatetimeIndex):
        days = (index.max().normalize() - index.min().normalize()).days + 1
        return float(days) / 365.25
    return n / float(periods_per_year)


