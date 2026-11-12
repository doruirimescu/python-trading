"""Round 2: the trend rule under stress: other averages, bands, monthly decisions, combinations, horizons, costs.

    python research/dca/round2.py [--years 10] [--set trend]
"""
import argparse

import pandas as pd

from perfectshape.dca.account import AccountConfig
from perfectshape.dca.data import load_market
from perfectshape.dca.evaluate import compare
from perfectshape.dca.policy import const, to_array, trend_policy, turn_of_month, vote_policy
from perfectshape.dca.signals import features

ERAS = [("all", None, None), ("62-89", "1962-01-01", "1989-12-31"), ("90-07", "1990-01-01", "2007-12-31"), ("08-26", "2008-01-01", None)]

fear = lambda g: (g["rv_ratio"] > 1.3) | (g["vix_pct"] > 0.8)
SETS = {
    "trend": {
        "dca": const(0), "early 6": const(-6), "tom": turn_of_month(4),
        **{f"trend {n}d": trend_policy(n) for n in (50, 100, 150, 200, 250, 300)},
        "trend 200d band 1%": trend_policy(200, band=0.01),
        "trend 200d band 2%": trend_policy(200, band=0.02),
        "trend 200d monthly": trend_policy(200, monthly=True),
        "trend 210d monthly (10 months)": trend_policy(210, monthly=True),
        "trend 200d, -3": trend_policy(200, on=-3),
        "trend 200d, off = hold 3": trend_policy(200, off=3),
        "trend 200d, off = hold 6": trend_policy(200, off=6),
        "trend 200d, off = -2": trend_policy(200, off=-2),
        "trend 200d on -5 + tom": trend_policy(200, on=-5, tom=1),
        "trend 200d monthly on -5 + tom": trend_policy(200, on=-5, tom=1, monthly=True),
        "trend 200d, not when yields jump": trend_policy(200, veto=lambda g: g["y10_chg"] > 0.6),
        "trend 200d, yields jump -> hold 3": trend_policy(200, veto=lambda g: g["y10_chg"] > 0.6, veto_to=3),
        "trend 200d or fear": lambda f: (trend_policy(200)(f).where(~fear(f.shift(1)).fillna(False), -6.0)),
        "votes x2": vote_policy(2.0),
    },
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--set", default="trend")
    ap.add_argument("--spread", type=float, default=0.0)
    ap.add_argument("--vs", default="dca")
    a = ap.parse_args()
    m = load_market()
    f = features(m)
    targets = {k: to_array(p, f) for k, p in SETS[a.set].items()}
    cfg = AccountConfig(borrow_spread=a.spread)
    rows = {}
    for era, first, last in ERAS:
        out = compare(m, targets, a.years, cfg, first, last, bench=a.vs)
        for k, v in out.items():
            r = rows.setdefault(k, {})
            r[f"{era} win"] = round(v["win"] * 100)
            r[f"{era} med"] = round(v["median"] * 100, 2)
            r[f"{era} worst"] = round(v["worst"] * 100, 2)
            if era == "all":
                r.update(n=v["n"], p10=round(v["p10"] * 100, 2), best=round(v["best"] * 100, 2), calls=v["calls"])
    pd.set_option("display.width", 250)
    print(f"{a.years}-year accounts, borrow at the 10-year yield + {a.spread:.1%}; edge over {a.vs}, % of final wealth")
    print(pd.DataFrame(rows).T.to_string())
