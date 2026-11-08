"""Exchange calendar helpers (NYSE weekday/holiday rules, tz utilities)."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import pandas as pd
from dateutil.easter import easter

ET = "America/New_York"


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


@lru_cache(maxsize=None)
def nyse_holidays(year: int) -> frozenset[dt.date]:
    h = {
        _observed(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),            # MLK
        _nth_weekday(year, 2, 0, 3),            # Presidents
        easter(year) - dt.timedelta(days=2),    # Good Friday
        _last_weekday(year, 5, 0),              # Memorial
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),            # Labor
        _nth_weekday(year, 11, 3, 4),           # Thanksgiving
        _observed(dt.date(year, 12, 25)),
    }
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))
    # Jan 1 observed on prior Dec 31 is not an NYSE holiday when Jan 1 is Saturday: drop it.
    h = {d for d in h if d.year == year}
    return frozenset(h)


def is_trading_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def trading_days(start, end) -> pd.DatetimeIndex:
    """Naive-date DatetimeIndex of NYSE trading days in [start, end]."""
    days = pd.bdate_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize())
    return pd.DatetimeIndex([d for d in days if is_trading_day(d.date())])


def to_exchange(idx: pd.DatetimeIndex, tz: str = ET) -> pd.DatetimeIndex:
    return idx.tz_convert(tz)


def local_to_utc(naive: pd.DatetimeIndex | pd.Series, tz: str = ET) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(naive).tz_localize(tz).tz_convert("UTC")


def hhmm_to_minutes(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def freq_to_timedelta(freq: str) -> pd.Timedelta:
    f = freq.lower()
    if f in ("1d", "d", "daily"):
        return pd.Timedelta(days=1)
    unit = f[-1]
    n = int(f[:-1] or 1)
    if unit == "m":
        return pd.Timedelta(minutes=n)
    if unit == "h":
        return pd.Timedelta(hours=n)
    if unit == "s":
        return pd.Timedelta(seconds=n)
    raise ValueError(f"unsupported freq {freq!r}")


def is_daily(freq: str) -> bool:
    return freq.lower() in ("1d", "d", "daily")
