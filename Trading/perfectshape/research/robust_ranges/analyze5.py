"""Absolute gates: success / P&L of candidates passing threshold rules (no per-scan top-N), train vs test years."""
import glob
import itertools
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/w2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["succ"] = ((df.f2_n_closed >= 2) & (df.f2_ret > 0)).astype(int)
df["n2"] = (df.f2_n_closed >= 2).astype(int)
df = df[df.score >= 0.6].copy()
df["exp2"] = df.trades_per_year * 2
df["train"] = df.year <= 2019
W = int(df.W.iloc[0])


def summary(d, label=""):
    tr, te = d[d.train], d[~d.train]
    ng = d.grp.nunique()
    top = d.sort_values("score", ascending=False).groupby("grp").head(10)
    return {"rule": label, "n": len(d), "groups": ng, "succ": d.succ.mean(), "n2": d.n2.mean(),
            "ret": d.f2_ret.mean(), "med": d.f2_ret.median(), "p_loss20": (d.f2_ret < -0.2).mean(),
            "succ_tr": tr.succ.mean(), "succ_te": te.succ.mean(), "ret_tr": tr.f2_ret.mean(),
            "ret_te": te.f2_ret.mean(), "top10_succ": top.succ.mean(), "top10_ret": top.f2_ret.mean()}


rows = [summary(df, "all passed")]
grid = {
    "trades_per_year": [None, 1.2, 1.5, 2.0],
    "band_over_vol": [None, 0.6, 0.5, 0.45],
    "leg_corr": [None, 0.7, 0.6],
    "vol_last_ratio": [None, 0.9, 1.0],
    "wf2_mean_rev": [None, 1.5, 2.0],
    "half_life": [None, 80, 60],
}
keys = list(grid)
for combo in itertools.product(*grid.values()):
    m = np.ones(len(df), bool)
    lab = []
    for k, v in zip(keys, combo):
        if v is None:
            continue
        if k in ("trades_per_year", "vol_last_ratio", "wf2_mean_rev"):
            m &= df[k].to_numpy() >= v
            lab.append(f"{k}>={v}")
        else:
            m &= df[k].to_numpy() <= v
            lab.append(f"{k}<={v}")
    if not lab or m.sum() < 300:
        continue
    rows.append(summary(df[m], " & ".join(lab)))
r = pd.DataFrame(rows)
r["cov"] = r.groups / df.grp.nunique()
print(f"W={W}: {len(df)} passed, {df.grp.nunique()} scans")
print(r.iloc[:1].round(3).to_string())
# best by train success, then show test
best = r[r.groups >= 0.3 * df.grp.nunique()].sort_values("succ_tr", ascending=False).head(25)
print("\n=== top rules by TRAIN success (>= 30% of scans keep a candidate) ===")
print(best.round(3).to_string())
best = r[r.groups >= 0.3 * df.grp.nunique()].sort_values("ret_tr", ascending=False).head(15)
print("\n=== top rules by TRAIN mean return ===")
print(best.round(3).to_string())
r.to_csv(f"rules_w{W}.csv", index=False)
