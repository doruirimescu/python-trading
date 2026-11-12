"""Does buying the dip pay? The S&P 500's next-month return over the 10-year yield (annualised), by drawdown from the
all-time high, by VIX and by the 200-day trend, in each era. Also the realised volatility that follows, which is what
Kelly sizing divides by.

    python research/dca/dip_explore.py
"""
import numpy as np
import pandas as pd

from perfectshape.dca.continuous import ERAS
from perfectshape.dca.pages import _markets


def table():
    M = _markets()
    m, f = M["all"], M["f_all"]
    r = m["tr"].pct_change()
    days = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1)
    ex = r - m["y10"] / 100.0 * days / 365.0
    g = f.shift(1)
    df = pd.DataFrame({"ex": ex, "r": r, "dd": g["dd_ath"], "vix": g["vix_like"], "trend": g["trend"]}, index=m.index)
    mon = df.groupby(m.index.to_period("M")).agg(ex=("ex", "sum"), vol=("r", "std"), dd=("dd", "first"),
                                                  vix=("vix", "first"), trend=("trend", "first")).dropna()
    mon["ex"] *= 12.0
    mon["vol"] *= np.sqrt(252)
    era = pd.Series("", index=mon.index)
    for e, (a, b) in ERAS.items():
        era[(mon.index >= pd.Period(a[:7], "M")) & (mon.index <= pd.Period(b[:7], "M"))] = e
    mon["era"] = era
    return mon


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    mon = table()
    mon["dd_b"] = pd.cut(-mon["dd"], [-0.01, 0.03, 0.10, 0.20, 0.35, 1.0], labels=["<3%", "3-10%", "10-20%", "20-35%", ">35%"])
    mon["vix_b"] = pd.cut(mon["vix"], [0, 15, 20, 25, 35, 200], labels=["<15", "15-20", "20-25", "25-35", ">35"])
    mon["state"] = np.where(mon["trend"] > 0, "above", "below")
    for col in ("dd_b", "vix_b"):
        for split in (None, "state"):
            keys = [col] + ([split] if split else [])
            t = mon.groupby(keys + ["era"], observed=True).agg(ex=("ex", "mean"), vol=("vol", "mean"), n=("ex", "size"))
            t["sharpe"] = t["ex"] / t["vol"]
            t["kelly"] = t["ex"] / t["vol"] ** 2
            print(f"\n== by {' x '.join(keys)} (mean annualised excess return over y10, vol that month, months)")
            print(t.unstack("era").round(3).to_string())
    pd.to_pickle(mon, "data_cache/dca/dip_months.pkl")
