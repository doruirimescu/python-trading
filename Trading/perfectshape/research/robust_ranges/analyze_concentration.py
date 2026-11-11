"""Does member concentration (drifted end weights, growth dispersion, top-stock share) predict forward success or breaks? Needs concentration.py output."""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
H = str(Path(__file__).resolve().parent) + "/"
NEW = ["w_end_max", "neff_min", "gdisp_max", "ts_full", "ts_last", "vol_last_vs_full", "member_share_max"]


def prep(tag):
    d = pd.read_pickle(H + f"{tag}_conc.pkl")
    d = d[d.score >= 0.6].copy()
    d["year"] = d["asof"].str[:4].astype(int)
    d["succ"] = ((d.f2_n_closed >= 2) & (d.f2_ret > 0)).astype(int)
    d["bad"] = (d.f2_ret < -0.2).astype(int)
    d["robust"] = (d.trades_per_year >= 1.5) & (d.band_over_vol <= 0.45) & (d.vol_last_ratio >= 1.0)
    return d


def auc(y, x):
    ok = np.isfinite(x)
    return roc_auc_score(y[ok], x[ok]) if len(np.unique(y[ok])) > 1 else np.nan


for tag in ("w2520", "w1260"):
    d = prep(tag)
    for sub_name, s in (("all passing", d), ("robust", d[d.robust])):
        print(f"\n=== {tag} {sub_name}: n {len(s)}, succ {s.succ.mean():.3f}, bad(<-20%) {s.bad.mean():.3f}, mean ret {s.f2_ret.mean():+.3f}")
        rows = []
        for f in NEW:
            ya = np.array([auc(g.succ.to_numpy(), g[f].to_numpy()) for _, g in s.groupby("year") if g.succ.nunique() > 1])
            yb = np.array([auc(g.bad.to_numpy(), g[f].to_numpy()) for _, g in s.groupby("year") if g.bad.nunique() > 1])
            rows.append({"feat": f, "auc_succ": auc(s.succ.to_numpy(), s[f].to_numpy()), "yr_succ_same": ((ya < .5).mean()),
                         "auc_bad": auc(s.bad.to_numpy(), s[f].to_numpy()), "yr_bad_same": ((yb > .5).mean()),
                         "sp_ret": s[[f, "f2_ret"]].corr("spearman").iloc[0, 1], "sp_maxout": s[[f, "f2_max_out"]].corr("spearman").iloc[0, 1]})
        print(pd.DataFrame(rows).round(3).to_string(index=False))
    for f in ("w_end_max", "ts_last", "gdisp_max"):
        s = d[d.robust]
        q = pd.cut(s[f], {"w_end_max": [0, .45, .5, .55, .6, .7, .8, 1.01], "ts_last": [0, .25, .3, .35, .4, .5, .6, 2],
                          "gdisp_max": [0, .5, 1, 1.5, 2, 3, 10]}[f])
        t = s.groupby(q, observed=True).agg(n=("succ", "size"), succ=("succ", "mean"), bad=("bad", "mean"), ret=("f2_ret", "mean"),
                                             med=("f2_ret", "median"), maxout=("f2_max_out", "median"))
        t["succ_tr"] = s[s.year <= 2019].groupby(q[s.year <= 2019], observed=True).succ.mean()
        t["succ_te"] = s[s.year >= 2020].groupby(q[s.year >= 2020], observed=True).succ.mean()
        t["bad_tr"] = s[s.year <= 2019].groupby(q[s.year <= 2019], observed=True).bad.mean()
        t["bad_te"] = s[s.year >= 2020].groupby(q[s.year >= 2020], observed=True).bad.mean()
        print(f"\n{tag} robust by {f}\n{t.round(3).to_string()}")
