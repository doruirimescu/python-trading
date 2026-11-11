"""Breakouts and multivariate models (leave-one-year-out)."""
import glob
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 300)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/w2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["succ"] = ((df.f2_n_closed >= 2) & (df.f2_ret > 0)).astype(int)
df["broke"] = (df.f2_max_out >= 3).astype(int)
df = df[df.score >= 0.6].copy()
print("passed rows", len(df), "groups", df.grp.nunique())
print("f2_ret quantiles", df.f2_ret.quantile([.05, .1, .25, .5, .75, .9, .95]).round(3).to_dict())
print("f2_max_out quantiles", df.f2_max_out.quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
print("broke rate %.3f; mean ret broke %.3f, not broke %.3f; succ rate not broke %.3f" % (
    df.broke.mean(), df[df.broke == 1].f2_ret.mean(), df[df.broke == 0].f2_ret.mean(), df[df.broke == 0].succ.mean()))
print(pd.crosstab(np.clip(df.f2_n_closed, 0, 5), df.broke, normalize=False))
print(df.groupby(np.clip(df.f2_n_closed, 0, 5)).f2_ret.agg(["mean", "median", "count"]).round(3))

skip = {"sector", "asof", "num", "den", "rank", "year", "grp", "succ", "broke", "W", "n_stocks"}
feats = [c for c in df.columns if c not in skip and not c.startswith(("f1_", "f2_"))]
# duplicates of the same quantity
for dup in ("swing_up", "swing_down", "per_trade", "half_band", "is_rev", "is_worst"):
    if dup in feats:
        feats.remove(dup)


def auc(y, x):
    ok = np.isfinite(x)
    return roc_auc_score(y[ok], x[ok]) if len(np.unique(y[ok])) > 1 else np.nan


rows = []
for f in feats:
    rows.append({"feat": f, "auc_broke": auc(df.broke.to_numpy(), df[f].to_numpy()),
                 "sp_ret": df[[f, "f2_ret"]].corr("spearman").iloc[0, 1],
                 "auc_succ": auc(df.succ.to_numpy(), df[f].to_numpy())})
r = pd.DataFrame(rows)
r["s"] = (r.auc_broke - 0.5).abs()
print("\n=== predictors of a breakout (fwd max beyond the band >= 3 half-bands) ===")
print(r.sort_values("s", ascending=False).head(30).round(3).to_string())

# multivariate, leave-one-year-out
X = df[feats].replace([np.inf, -np.inf], np.nan).to_numpy(float)
years = sorted(df.year.unique())
for target in ("succ", "broke"):
    y = df[target].to_numpy()
    pred = np.full(len(df), np.nan)
    for yr in years:
        tr, te = df.year.to_numpy() != yr, df.year.to_numpy() == yr
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=200)
        m.fit(X[tr], y[tr])
        pred[te] = m.predict_proba(X[te])[:, 1]
    df[f"p_{target}"] = pred
    print(f"\n{target}: LOYO AUC {roc_auc_score(y, pred):.3f}; per year:",
          {yr: round(roc_auc_score(y[df.year == yr], pred[df.year == yr]), 3) for yr in years
           if len(np.unique(y[df.year == yr])) > 1})
    m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=200).fit(X, y)
    sub = np.random.default_rng(0).choice(len(df), min(8000, len(df)), replace=False)
    pi = permutation_importance(m, X[sub], y[sub], scoring="roc_auc", n_repeats=3, random_state=0)
    imp = pd.Series(pi.importances_mean, index=feats).sort_values(ascending=False)
    print(imp.head(15).round(4).to_string())

# deciles of the out-of-sample model prediction
for target in ("succ",):
    q = pd.qcut(df[f"p_{target}"], 10, labels=False)
    print(f"\nby decile of p_{target} (out-of-sample):")
    print(df.groupby(q).agg(p=(f"p_{target}", "mean"), succ=("succ", "mean"), broke=("broke", "mean"),
                            ret=("f2_ret", "mean"), med_ret=("f2_ret", "median"), n2=("f2_n_closed", "mean")).round(3))
df.to_pickle("passed_with_preds.pkl")
