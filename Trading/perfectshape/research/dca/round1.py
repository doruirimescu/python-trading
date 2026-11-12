"""Round 1: simple policies against plain DCA over every start month, by horizon and era.

    python research/dca/round1.py [--years 10]
"""
import argparse

import numpy as np
import pandas as pd

from perfectshape.dca.account import AccountConfig
from perfectshape.dca.data import load_market
from perfectshape.dca.evaluate import compare
from perfectshape.dca.policy import const, to_array, turn_of_month, vote_policy, when
from perfectshape.dca.signals import features

ERAS = [("all", None, None), ("1962-89", "1962-01-01", "1989-12-31"), ("1990-2007", "1990-01-01", "2007-12-31"),
        ("2008-26", "2008-01-01", None)]

POLICIES = {
    "dca": const(0),
    "hold 1 (always a month late)": const(1),
    "hold 6": const(6),
    "early 1 (always a month ahead)": const(-1),
    "early 3": const(-3),
    "early 6 (always max ahead)": const(-6),
    "turn of month (4 days early)": turn_of_month(4),
    "turn of month + early 5": turn_of_month(4, base=-5),
    "wait for a 5% dip, else hold": when(lambda g: g["dd"] < -0.05, 0, 6),
    "borrow on a 10% drawdown": when(lambda g: g["dd"] < -0.10, -6, 0),
    "borrow above 200d avg": when(lambda g: g["trend"] > 0, -6, 0),
    "borrow below 200d avg": when(lambda g: g["trend"] < 0, -6, 0),
    "borrow on fear (vol spike / high VIX)": when(lambda g: (g["rv_ratio"] > 1.3) | (g["vix_pct"] > 0.8), -6, 0),
    "borrow unless yields rising": when(lambda g: g["y10_chg"] < 0.25, -6, 0),
    "early 6, hold when yields jump": when(lambda g: g["y10_chg"] > 0.6, 3, -6),
    "votes x2": vote_policy(2.0),
    "votes x2 + tom": vote_policy(2.0, tom=True),
    "votes x2, base -2": vote_policy(2.0, base=-2.0),
    "votes x3, base -3 + tom": vote_policy(3.0, base=-3.0, tom=True),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--vs", default="dca")
    a = ap.parse_args()
    m = load_market()
    f = features(m)
    targets = {k: to_array(p, f) for k, p in POLICIES.items()}
    pd.set_option("display.width", 250)
    for era, first, last in ERAS:
        out = compare(m, targets, a.years, AccountConfig(), first, last, bench=a.vs)
        if not out:
            continue
        rows = [{"policy": k, **{c: v[c] for c in ("win", "median", "mean", "p10", "worst", "best", "usd_median", "interest", "calls")}}
                for k, v in out.items()]
        d = pd.DataFrame(rows)
        for c in ("win", "median", "mean", "p10", "worst", "best"):
            d[c] = (d[c] * 100).round(2)
        n = next(iter(out.values()))["n"]
        print(f"\n=== {a.years}-year accounts, {era}: {n} start months; edge over {a.vs} in % of final wealth")
        print(d.round(0).assign(**{c: d[c] for c in ("win", "median", "mean", "p10", "worst", "best")}).to_string(index=False))
    print("\ntime in each target (all history):")
    for k, t in targets.items():
        print(f"  {k:<40} mean {t.mean():+.2f}  share borrowed {(t < 0).mean():.0%}  share holding {(t > 0).mean():.0%}  changes/yr {(np.diff(t) != 0).sum() / (len(t) / 252):.0f}")
