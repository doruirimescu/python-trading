"""Daily market history for the DCA study, one DataFrame on the S&P 500's trading calendar from 1962.

Columns (NaN before a series exists):

* ``tr``     S&P 500 total return index: ^SP500TR from 1988; before that the price index plus Shiller's monthly
             dividend yield, chained.
* ``px``     S&P 500 price index (^GSPC): signals such as trend and drawdown use it.
* ``y10``    10-year Treasury yield, percent a year (^TNX): the margin rate of the study.
* ``y3m``    13-week T-bill yield (^IRX): what idle cash earns.
* ``vix``, ``vix3m``, ``skew``   CBOE indices (1990, 2006, 1990).
* ``hy``, ``ust``   total-return prices of a high-yield fund (VWEHX, 1980) and an intermediate Treasury fund
             (VFITX, 1991): their ratio is the credit signal.
* ``epu``    daily US Economic Policy Uncertainty index (Baker, Bloom, Davis): counts of newspaper articles, the
             study's news series (1985).

Everything is cached in ``data_cache/dca/market.pkl``.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from perfectshape.universe import PROJECT_ROOT

log = logging.getLogger(__name__)

YAHOO = {"px": "^GSPC", "sp500tr": "^SP500TR", "y10": "^TNX", "y3m": "^IRX", "vix": "^VIX", "vix3m": "^VIX3M",
         "skew": "^SKEW", "hy": "VWEHX", "ust": "VFITX"}
EPU_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"
SHILLER_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
START = "1961-01-01"


def _yahoo(ticker: str, adjusted: bool):
    import yfinance as yf

    df = yf.download(ticker, start=START, auto_adjust=adjusted, progress=False)
    s = df["Close"]
    s = s.iloc[:, 0] if getattr(s, "ndim", 1) > 1 else s
    s = s.dropna()
    s.index = s.index.tz_localize(None) if getattr(s.index, "tz", None) is not None else s.index
    return s.astype(float)


def _epu():
    import pandas as pd
    import requests

    r = requests.get(EPU_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df = df[pd.to_numeric(df["year"], errors="coerce").notna()]
    idx = pd.to_datetime(dict(year=df["year"].astype(int), month=df["month"].astype(int), day=df["day"].astype(int)))
    return pd.Series(df["daily_policy_index"].astype(float).to_numpy(), index=idx).sort_index()


def _shiller_dividend_yield():
    """Monthly dividend / price of the S&P Composite (a year's dividends over the price), indexed by month start."""
    import pandas as pd
    import requests

    r = requests.get(SHILLER_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    x = pd.read_excel(io.BytesIO(r.content), sheet_name="Data", header=7)
    x = x[pd.to_numeric(x["Date"], errors="coerce").notna()]
    ym = x["Date"].astype(float)
    year = np.floor(ym).astype(int)
    month = np.round((ym - year) * 100).astype(int).clip(1, 12)
    idx = pd.to_datetime(dict(year=year, month=month, day=1))
    dy = pd.to_numeric(x["D"], errors="coerce") / pd.to_numeric(x["P"], errors="coerce")
    return pd.Series(dy.to_numpy(), index=idx).dropna()


def load_market(cache_dir: str | Path | None = None, today: date | None = None, max_age_days: int = 3):
    """The study's DataFrame (see the module docstring), downloaded at most every ``max_age_days``."""
    import pandas as pd

    today = today or date.today()
    cache_dir = Path(cache_dir or os.environ.get("PERFECTSHAPE_DCA_CACHE", PROJECT_ROOT / "data_cache" / "dca"))
    path = cache_dir / "market.pkl"
    if path.exists() and (today - date.fromtimestamp(path.stat().st_mtime)) < timedelta(days=max_age_days):
        return pd.read_pickle(path)
    import logging as _l
    _l.getLogger("yfinance").setLevel(_l.CRITICAL)
    raw = {k: _yahoo(t, adjusted=k in ("hy", "ust")) for k, t in YAHOO.items()}
    px = raw["px"][raw["px"].index >= "1962-01-02"]
    df = pd.DataFrame(index=px.index)
    df["px"] = px
    for k in ("y10", "y3m", "vix", "vix3m", "skew", "hy", "ust"):
        df[k] = raw[k].reindex(df.index).ffill(limit=5)
    try:
        df["epu"] = _epu().reindex(df.index.union(_epu().index)).ffill(limit=5).reindex(df.index)
    except Exception as e:                                        # the study runs without the news series
        log.warning("dca data: no policy-uncertainty index (%s)", e)
        df["epu"] = np.nan
    # total return: the official index where it exists, price + dividends before
    ret = df["px"].pct_change().fillna(0.0)
    try:
        dy = _shiller_dividend_yield().reindex(df.index, method="ffill")
    except Exception as e:
        log.warning("dca data: no Shiller dividends (%s); 3%% a year is assumed before 1988", e)
        dy = pd.Series(0.03, index=df.index)
    tr_ret = ret + dy.fillna(0.03) / 252.0
    official = raw["sp500tr"].reindex(df.index)
    has = official.notna()
    tr_ret[has & has.shift(1, fill_value=False)] = official.pct_change()[has & has.shift(1, fill_value=False)]
    df["tr"] = (1.0 + tr_ret).cumprod()
    df["y10"] = df["y10"].ffill()
    df["y3m"] = df["y3m"].ffill()
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


COLUMNS = ["px", "y10", "y3m", "vix", "vix3m", "skew", "hy", "ust", "epu", "tr"]


def frame_from_prices(px, y10, y3m=None, tr=None):
    """A study frame for any price series: missing signal columns are NaN (policies treat them as absent), the
    total-return index defaults to the price itself, cash earns nothing unless ``y3m`` is given."""
    import pandas as pd

    df = pd.DataFrame(index=px.index, columns=COLUMNS, dtype=float)
    df["px"] = px
    df["tr"] = px if tr is None else tr.reindex(px.index)
    df["y10"] = y10.reindex(px.index.union(y10.index)).ffill().reindex(px.index).bfill()
    df["y3m"] = 0.0 if y3m is None else y3m.reindex(px.index.union(y3m.index)).ffill().reindex(px.index).fillna(0.0)
    return df


def load_early_history(cache_dir: str | Path | None = None):
    """S&P 500 (its 90-stock predecessor before 1957) from 1928 to 1961, daily: price from ^GSPC, dividends and
    the long government yield from Shiller's monthly table; cash earns nothing. Out of sample for everything in
    the study, which was built on 1962 onwards."""
    import pandas as pd

    cache_dir = Path(cache_dir or os.environ.get("PERFECTSHAPE_DCA_CACHE", PROJECT_ROOT / "data_cache" / "dca"))
    path = cache_dir / "early.pkl"
    if path.exists():
        return pd.read_pickle(path)
    import requests
    import yfinance as yf

    px = yf.download("^GSPC", start="1927-01-01", end="1962-01-02", auto_adjust=False, progress=False)["Close"]
    px = (px.iloc[:, 0] if getattr(px, "ndim", 1) > 1 else px).dropna().astype(float)
    px.index = px.index.tz_localize(None) if getattr(px.index, "tz", None) is not None else px.index
    r = requests.get(SHILLER_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    x = pd.read_excel(io.BytesIO(r.content), sheet_name="Data", header=7)
    x = x[pd.to_numeric(x["Date"], errors="coerce").notna()]
    ym = x["Date"].astype(float)
    year = np.floor(ym).astype(int)
    idx = pd.to_datetime(dict(year=year, month=np.round((ym - year) * 100).astype(int).clip(1, 12), day=1))
    gs10 = pd.Series(pd.to_numeric(x["Rate GS10"], errors="coerce").to_numpy(), index=idx).dropna()
    dy = pd.Series((pd.to_numeric(x["D"], errors="coerce") / pd.to_numeric(x["P"], errors="coerce")).to_numpy(), index=idx).dropna()
    dyd = dy.reindex(px.index.union(dy.index)).ffill().reindex(px.index)
    tr = (1.0 + px.pct_change().fillna(0.0) + dyd / 252.0).cumprod()
    df = frame_from_prices(px, gs10, tr=tr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def load_other_market(ticker: str, cache_dir: str | Path | None = None):
    """Another index from Yahoo with US yields as the borrowing and cash rates (a robustness check, not a model of
    a local saver). Price indices carry no dividends: that understates what borrowing to invest earned."""
    import pandas as pd

    cache_dir = Path(cache_dir or os.environ.get("PERFECTSHAPE_DCA_CACHE", PROJECT_ROOT / "data_cache" / "dca"))
    path = cache_dir / f"other_{ticker.strip('^').replace('=', '_')}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    us = load_market(cache_dir)
    px = _yahoo(ticker, adjusted=True)
    px = px[px.index >= "1962-01-02"]
    df = frame_from_prices(px, us["y10"], us["y3m"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df
