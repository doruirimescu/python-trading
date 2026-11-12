"""Why the trend rule works, and how much timing could add at most.

1. The S&P 500's return over the 10-year yield in months that start above / below the 200-day average, by era.
2. Perfect foresight: the edge of a saver who knows every future price, for a sample of 10-year accounts.

    python research/dca/why.py
"""
import numpy as np
import pandas as pd

from perfectshape.dca.account import AccountConfig, best_possible, simulate
from perfectshape.dca.data import load_early_history, load_market
from perfectshape.dca.evaluate import windows
from perfectshape.dca.policy import to_array, trend_policy
from perfectshape.dca.signals import features

if __name__ == "__main__":
    pd.set_option("display.width", 200)
    m = pd.concat([load_early_history(), load_market()])
    m = m[~m.index.duplicated(keep="last")]
    m["tr"] = (1 + pd.concat([load_early_history()["tr"].pct_change(), load_market()["tr"].pct_change()]).fillna(0)
               .loc[m.index]).cumprod()
    f = features(m)
    on = pd.Series(to_array(trend_policy(200, monthly=True), f), index=m.index) < 0
    r = m["tr"].pct_change().fillna(0.0)
    days = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1)
    ex = r - m["y10"] / 100 * days / 365
    mon = pd.DataFrame({"ex": ex, "r": r, "on": on}).groupby(m.index.to_period("M")).agg(ex=("ex", "sum"), r=("r", lambda x: (1 + x).prod() - 1), on=("on", "first"))
    print("monthly S&P 500 return over the 10-year yield, by the trend state on payment day:")
    for name, s, e in [("1928-61", "1928", "1961"), ("1962-89", "1962", "1989"), ("1990-2007", "1990", "2007"), ("2008-26", "2008", "2026"), ("all", "1928", "2026")]:
        x = mon[s:e]
        row = []
        for st, lab in ((True, "above"), (False, "below")):
            v = x.loc[x.on == st, "ex"]
            row.append(f"{lab}: {len(v):4d} months, {v.mean() * 12:+6.1%}/yr, vol {v.std() * np.sqrt(12):5.1%}, t {v.mean() / v.std() * np.sqrt(len(v)):+.1f}, worst month {x.loc[x.on == st, 'r'].min():+.0%}")
        a, b = x.loc[x.on, "ex"], x.loc[~x.on, "ex"]
        d = a.mean() - b.mean()
        t = d / np.sqrt(a.var() / len(a) + b.var() / len(b))
        print(f"  {name:<10} " + " | ".join(row) + f" | difference t {t:+.1f}")
    # perfect foresight on a sample of 10-year accounts (S&P 500 1962-2026)
    m2 = load_market()
    f2 = features(m2)
    dates = m2.index.values.astype("datetime64[D]")
    tr, y10, y3m = m2["tr"].to_numpy(), m2["y10"].to_numpy(), m2["y3m"].to_numpy()
    cfg = AccountConfig()
    z = np.zeros(len(tr))
    tg = to_array(trend_policy(200, monthly=True), f2)
    for years in (10, 30):
        w = windows(dates, years, step=6)
        fore, trend, early = [], [], []
        for s, e in zip(w.starts, w.ends):
            base = simulate(tr, dates, z, y10, y3m, cfg, np.array([s]), np.array([e]))["wealth"][0]
            best = best_possible(tr, dates, y10, y3m, cfg, start=s, end=e)
            fore.append(simulate(tr, dates, best, y10, y3m, cfg, np.array([s]), np.array([e]))["wealth"][0] / base - 1)
            trend.append(simulate(tr, dates, tg, y10, y3m, cfg, np.array([s]), np.array([e]))["wealth"][0] / base - 1)
            early.append(simulate(tr, dates, z - 6, y10, y3m, cfg, np.array([s]), np.array([e]))["wealth"][0] / base - 1)
        fore, trend, early = map(np.array, (fore, trend, early))
        print(f"\n{years}-year accounts ({len(fore)} start months): edge over DCA, median [min .. max]")
        for nm, v in (("perfect foresight", fore), ("trend monthly", trend), ("always 6 ahead", early)):
            print(f"  {nm:<18} {np.median(v):+.1%} [{v.min():+.1%} .. {v.max():+.1%}]")
        print(f"  trend captures {np.median(trend / fore):.0%} of the ceiling (median)")
