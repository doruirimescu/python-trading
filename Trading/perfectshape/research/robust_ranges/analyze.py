"""Which in-sample features predict forward success of a scan-window band?"""
import glob
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/w2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["succ"] = ((df.f2_n_closed >= 2) & (df.f2_ret > 0)).astype(int)
df["succ_n2"] = (df.f2_n_closed >= 2).astype(int)
df["succ1"] = ((df.f1_n_closed >= 1) & (df.f1_ret > 0)).astype(int)
df["passed"] = df.score >= 0.6
print("rows", len(df), "groups", df.grp.nunique(), "passed", df.passed.sum())
print("base rates (all / passed): succ %.3f / %.3f, n>=2 %.3f / %.3f, f2_ret mean %.3f / %.3f" % (
    df.succ.mean(), df[df.passed].succ.mean(), df.succ_n2.mean(), df[df.passed].succ_n2.mean(),
    df.f2_ret.mean(), df[df.passed].f2_ret.mean()))
print(df.groupby("year")[["succ", "succ_n2", "f2_ret"]].mean().round(3).T)
print(df.groupby("sector")[["succ", "succ_n2", "f2_ret"]].mean().round(3).T)

skip = {"sector", "asof", "num", "den", "rank", "year", "grp", "succ", "succ_n2", "succ1", "passed", "W", "n_stocks"}
feats = [c for c in df.columns if c not in skip and not c.startswith(("f1_", "f2_"))]


def auc(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, int)
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]
    p, n = y.sum(), len(y) - y.sum()
    if p == 0 or n == 0:
        return np.nan
    r = pd.Series(x).rank().to_numpy()
    return (r[y == 1].sum() - p * (p + 1) / 2) / (p * n)


def within_auc(d, f, target="succ"):
    vals, w = [], []
    for _, g in d.groupby("grp"):
        a = auc(g[f], g[target])
        if np.isfinite(a):
            vals.append(a)
            w.append(min(g[target].sum(), len(g) - g[target].sum()))
    if not vals:
        return np.nan, np.nan
    vals, w = np.array(vals), np.array(w, float)
    return np.average(vals, weights=w), (vals > 0.5).mean()


rows = []
for pop_name, d in (("all", df), ("passed", df[df.passed])):
    for f in feats:
        ga = auc(d[f], d.succ)
        wa, share = within_auc(d, f)
        sp = d[[f, "f2_ret"]].corr(method="spearman").iloc[0, 1]
        # per-year global AUC consistency
        ya = [auc(g[f], g.succ) for _, g in d.groupby("year")]
        ya = np.array([a for a in ya if np.isfinite(a)])
        rows.append({"pop": pop_name, "feat": f, "auc": ga, "within_auc": wa, "grp_share>0.5": share,
                     "spearman_ret": sp, "yr_auc_min": ya.min(), "yr_auc_max": ya.max(),
                     "yr_same_side": max((ya > 0.5).mean(), (ya < 0.5).mean())})
res = pd.DataFrame(rows)
res["strength"] = (res.auc - 0.5).abs()
for pop_name in ("all", "passed"):
    print(f"\n=== {pop_name}: features by |AUC - 0.5| (succ = >=2 fwd reversions and fwd P&L > 0) ===")
    print(res[res["pop"] == pop_name].sort_values("strength", ascending=False).drop(columns=["pop"]).round(3).to_string())
res.to_csv("feature_auc.csv", index=False)
