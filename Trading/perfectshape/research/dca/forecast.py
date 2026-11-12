"""What predicts the S&P 500's return over the margin rate? Every signal, by fifths, in three eras.

For a saver the question is never "will stocks fall" but "is a payment better invested now or in h days": the
forward total return minus the 10-year yield over the same days (the cost of borrowing it) for h = 21, 63, 126.

    python research/dca/forecast.py [--h 63]
"""
import argparse

import pandas as pd

from perfectshape.dca.data import load_market
from perfectshape.dca.signals import features

ERAS = [("1962-89", "1962-01-01", "1989-12-31"), ("1990-2007", "1990-01-01", "2007-12-31"), ("2008-26", "2008-01-01", "2030-01-01")]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--h", type=int, default=63)
    a = ap.parse_args()
    df = load_market()
    f = features(df)
    h = a.h
    fwd = df["tr"].shift(-h) / df["tr"] - 1.0
    cost = (df["y10"] / 100.0 / 252.0).rolling(h).sum().shift(-h)
    ex = (fwd - cost) * 252.0 / h                    # annualised excess over the margin rate
    pd.set_option("display.width", 250)
    print(f"forward {h}-day S&P 500 total return over the 10-year yield, annualised; unconditional by era:")
    for name, s, e in ERAS:
        x = ex[s:e].dropna()
        print(f"  {name}: mean {x.mean():+.1%}  share of days positive {(x > 0).mean():.0%}  n={len(x)}")
    rows = []
    for col in [c for c in f.columns if c not in ("tdom", "tdleft")]:
        for name, s, e in ERAS:
            x = pd.DataFrame({"f": f[col], "ex": ex})[s:e].dropna()
            if len(x) < 1000:
                continue
            q = pd.qcut(x["f"].rank(method="first"), 5, labels=False)
            m = x.groupby(q)["ex"].mean()
            p = x.groupby(q)["ex"].apply(lambda v: (v > 0).mean())
            ic = x["f"].rank().corr(x["ex"].rank())
            rows.append({"signal": col, "era": name, **{f"q{i + 1}": m[i] for i in range(5)}, "q5-q1": m[4] - m[0],
                         "pos_q1": p[0], "pos_q5": p[4], "ic": ic,
                         "lo": x["f"].quantile(0.2), "hi": x["f"].quantile(0.8)})
    out = pd.DataFrame(rows)
    for c in ("q1", "q2", "q3", "q4", "q5", "q5-q1", "pos_q1", "pos_q5"):
        out[c] = (out[c] * 100).round(0)
    print(out.round(3).to_string(index=False))
    # calendar: mean daily total return by trading day of the month
    r = df["tr"].pct_change()
    print("\nmean daily return (bp) by trading days left in the month / trading day of the month, by era:")
    for name, s, e in ERAS:
        x = pd.DataFrame({"r": r, "left": f["tdleft"], "dom": f["tdom"]})[s:e].dropna()
        left = x.groupby("left")["r"].mean().head(6) * 1e4
        dom = x.groupby("dom")["r"].mean().head(6) * 1e4
        print(f"  {name}: left 5..0 " + " ".join(f"{left[i]:+.1f}" for i in range(5, -1, -1)) + " | day 1..6 "
              + " ".join(f"{dom[i]:+.1f}" for i in range(1, 7)) + f" | all days {x['r'].mean() * 1e4:+.1f}")
