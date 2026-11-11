"""Trends: what predicts that a 10-year ratio uptrend keeps rising over the next 1-2 years?"""
import glob
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/trend2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["up2"] = (df.f2_ret > 0).astype(int)
df["up1"] = (df.f1_ret > 0).astype(int)
df["held"] = (df.f2_below_channel == 0).astype(int)
p = df[df.score >= 0.6].copy()
print(f"rows {len(df)}, passing {len(p)}, scans {p.grp.nunique()}")
for nm, d in (("all", df), ("passing", p)):
    print(f"{nm}: up over 2y {d.up2.mean():.3f}, up over 1y {d.up1.mean():.3f}, stayed above channel {d.held.mean():.3f}, "
          f"mean 2y log move {d.f2_ret.mean():+.3f} (pair {d.f2_pair.mean():+.3f}), median {d.f2_ret.median():+.3f}, "
          f"2y move / fitted slope {d.f2_vs_slope.median():.2f}")
print(p.groupby("year").agg(n=("up2", "size"), up2=("up2", "mean"), ret=("f2_ret", "mean"), held=("held", "mean")).round(3).T.to_string())

skip = {"sector", "asof", "num", "den", "rank", "year", "grp", "up2", "up1", "held", "W"}
feats = [c for c in p.columns if c not in skip and not c.startswith(("f1_", "f2_"))]


def auc(y, x):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    return roc_auc_score(y[ok], x[ok]) if len(np.unique(y[ok])) > 1 else np.nan


rows = []
for f in feats:
    ya = [auc(g.up2.to_numpy(), g[f].to_numpy()) for _, g in p.groupby("year")]
    ya = np.array([a for a in ya if np.isfinite(a)])
    rows.append({"feat": f, "auc_up2": auc(p.up2.to_numpy(), p[f].to_numpy()),
                 "auc_held": auc(p.held.to_numpy(), p[f].to_numpy()),
                 "sp_ret": p[[f, "f2_ret"]].corr("spearman").iloc[0, 1],
                 "yr_min": ya.min(), "yr_max": ya.max(), "yr_same": max((ya > .5).mean(), (ya < .5).mean())})
r = pd.DataFrame(rows)
r["s"] = (r.auc_up2 - 0.5).abs()
print(r.sort_values("s", ascending=False).round(3).to_string(index=False))

for f in r.sort_values("s", ascending=False).feat.head(6):
    q = pd.qcut(p[f].rank(method="first"), 5, labels=False)
    t = p.groupby(q).agg(lo=(f, "min"), hi=(f, "max"), up2=("up2", "mean"), ret=("f2_ret", "mean"), held=("held", "mean"))
    t["up2_tr"] = p[p.year <= 2019].groupby(q[p.year <= 2019]).up2.mean()
    t["up2_te"] = p[p.year >= 2020].groupby(q[p.year >= 2020]).up2.mean()
    print(f"\n{f}\n{t.round(3).to_string()}")

X = p[feats].replace([np.inf, -np.inf], np.nan).to_numpy(float)
y = p.up2.to_numpy()
pred = np.full(len(p), np.nan)
for yr in sorted(p.year.unique()):
    tr, te = p.year.to_numpy() != yr, p.year.to_numpy() == yr
    m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=200).fit(X[tr], y[tr])
    pred[te] = m.predict_proba(X[te])[:, 1]
print(f"\nGBM leave-one-year-out AUC (up over 2y): {roc_auc_score(y, pred):.3f}")
q = pd.qcut(pred, 5, labels=False)
print(p.assign(q=q).groupby("q").agg(up2=("up2", "mean"), ret=("f2_ret", "mean"), pair=("f2_pair", "mean")).round(3).T.to_string())
