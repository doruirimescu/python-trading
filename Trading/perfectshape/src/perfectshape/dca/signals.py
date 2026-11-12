"""Market signals for the DCA study. Row t of every column uses data up to the close of day t only; policies
shift them one day before trading on them.

Price action: ``dd`` (drawdown from the 1-year high), ``dd_ath`` (from the all-time high), ``trend`` (price over
its 200-day average - 1), ``mom12`` (12-month return skipping the last month), ``ret21`` / ``ret5`` (last month /
week), ``rv21`` (realised volatility of the last month, a year), ``rv_ratio`` (that over its 1-year median:
volatility clusters), ``vol_long`` (realised volatility of the last 10 years). Options: ``vix``, ``vix_pct`` (rank in the last 5 years), ``vrp`` (VIX - realised),
``term`` (VIX / 3-month VIX: above 1 = stress), ``skew``. Rates: ``y10``, ``y10_chg`` (6-month change),
``curve`` (10-year - 3-month), ``real_carry`` (trailing 5-year stock return a year - 10-year yield). Credit:
``credit`` (high-yield fund over Treasury fund, against its 200-day average). News: ``epu`` (policy-uncertainty
index, last month over the last 2 years' median). Calendar: ``tdom`` (trading day of the month, 1 = first),
``tdleft`` (trading days left in the month, 0 = last).
"""

from __future__ import annotations

import numpy as np


def trading_day_of_month(index):
    import pandas as pd

    ym = pd.Series(index.year * 100 + index.month, index=index)
    tdom = ym.groupby(ym).cumcount() + 1
    size = ym.groupby(ym).transform("size")
    return tdom, size - tdom


def features(df):
    """DataFrame of signals on ``df``'s index (see the module docstring)."""
    import pandas as pd

    px = df["px"]
    lr = np.log(px).diff()
    f = pd.DataFrame(index=df.index)
    f["px"] = px
    f["dd"] = px / px.rolling(252, min_periods=126).max() - 1.0
    f["dd_ath"] = px / px.cummax() - 1.0
    f["trend"] = px / px.rolling(200).mean() - 1.0
    f["mom12"] = px.shift(21) / px.shift(252) - 1.0
    f["ret21"] = px / px.shift(21) - 1.0
    f["ret5"] = px / px.shift(5) - 1.0
    f["rv21"] = lr.rolling(21).std() * np.sqrt(252) * 100.0
    f["rv_ratio"] = f["rv21"] / f["rv21"].rolling(252, min_periods=126).median()
    # long-run volatility: the last 10 years' realised volatility (a year, %; from 1 year of data on)
    f["vol_long"] = lr.rolling(2520, min_periods=252).std() * np.sqrt(252) * 100.0
    f["vix"] = df["vix"]
    # implied volatility for every year: the VIX where it exists (1990 on), before that realised volatility
    # scaled by the VIX's typical premium over it (median VIX / realised, 1990 to today; one constant)
    both = (df["vix"] / f["rv21"]).dropna()
    scale = float(both.median()) if len(both) > 250 else 1.2
    f["vix_like"] = df["vix"].where(df["vix"].notna(), f["rv21"] * scale)
    f["vix_pct"] = df["vix"].rolling(1260, min_periods=252).rank(pct=True)
    f["vrp"] = df["vix"] - f["rv21"]
    f["term"] = df["vix"] / df["vix3m"]
    f["skew"] = df["skew"]
    f["y10"] = df["y10"]
    f["y3m"] = df["y3m"]
    f["y10_chg"] = df["y10"] - df["y10"].shift(126)
    f["curve"] = df["y10"] - df["y3m"]
    f["real_carry"] = ((df["tr"] / df["tr"].shift(1260)) ** (1 / 5) - 1.0) * 100.0 - df["y10"]
    ratio = df["hy"] / df["ust"]
    f["credit"] = ratio / ratio.rolling(200).mean() - 1.0
    f["hy_ret63"] = df["hy"] / df["hy"].shift(63) - 1.0
    epu = df["epu"].rolling(21, min_periods=10).mean()
    f["epu"] = epu / epu.rolling(504, min_periods=252).median()
    f["tdom"], f["tdleft"] = trading_day_of_month(df.index)
    return f
