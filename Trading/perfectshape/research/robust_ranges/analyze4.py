"""Transparent models: logistic regression on a few features (LOYO), vs gradient boosting."""
import glob
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/w2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["succ"] = ((df.f2_n_closed >= 2) & (df.f2_ret > 0)).astype(int)
df = df[df.score >= 0.6].copy()
# transforms
df["log_height"] = np.log(df.height)
df["log_hl"] = np.log(np.clip(df.half_life, 5, 2000))
df["log_bov"] = np.log(df.band_over_vol)
df["log_tpy"] = np.log(df.trades_per_year + 0.1)
df["log_vlr"] = np.log(df.vol_last_ratio)
df["log_vol"] = np.log(df.vol)
df["band_edge"] = np.abs(df.band_pos - 0.5)          # distance of today's level from the median, in band widths
print("rows", len(df), "groups", df.grp.nunique(), "succ", round(df.succ.mean(), 3))

SETS = {
    "tpy": ["log_tpy"],
    "bov": ["log_bov"],
    "tpy+bov": ["log_tpy", "log_bov"],
    "core4": ["log_tpy", "log_bov", "leg_corr", "log_vlr"],
    "core6": ["log_tpy", "log_bov", "leg_corr", "log_vlr", "wf2_mean_rev", "band_edge"],
    "core8": ["log_tpy", "log_bov", "leg_corr", "log_vlr", "wf2_mean_rev", "band_edge", "log_height", "nb_mean"],
    "core8+m": ["log_tpy", "log_bov", "leg_corr", "log_vlr", "wf2_mean_rev", "band_edge", "log_height", "nb_mean",
                "member_share_max", "member_vol_max", "ratio_vs_member_vol"],
    "no_nb": ["log_tpy", "log_bov", "leg_corr", "log_vlr", "wf2_mean_rev", "band_edge", "log_height",
              "member_share_max", "ratio_vs_member_vol"],
}
years = sorted(df.year.unique())
y = df.succ.to_numpy()
yr = df.year.to_numpy()


def loyo(make, cols):
    X = df[cols].to_numpy(float)
    pred = np.full(len(df), np.nan)
    for v in years:
        tr, te = yr != v, yr == v
        m = make().fit(X[tr], y[tr])
        pred[te] = m.predict_proba(X[te])[:, 1]
    return pred


def top_rate(pred, n=10):
    d = df.assign(p=pred).sort_values("p", ascending=False).groupby("grp").head(n)
    return d.succ.mean(), d.f2_ret.mean()


base = df.sort_values("score", ascending=False).groupby("grp").head(10)
print(f"baseline top10 by score: succ {base.succ.mean():.3f} ret {base.f2_ret.mean():+.3f}")
for name, cols in SETS.items():
    lr = loyo(lambda: __import__("sklearn.pipeline", fromlist=["make_pipeline"]).make_pipeline(
        StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)), cols)
    s, r = top_rate(lr)
    print(f"LR  {name:8s} AUC {roc_auc_score(y, lr):.3f}  top10/scan succ {s:.3f} ret {r:+.3f}")
gb = loyo(lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=200),
          SETS["core8+m"])
s, r = top_rate(gb)
print(f"GBM core8+m AUC {roc_auc_score(y, gb):.3f}  top10/scan succ {s:.3f} ret {r:+.3f}")

# full-sample LR coefficients (standardised) for the interpretable set
from sklearn.pipeline import make_pipeline  # noqa: E402
for name in ("core6", "no_nb"):
    cols = SETS[name]
    pipe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(df[cols], y)
    sc, lr = pipe.named_steps["standardscaler"], pipe.named_steps["logisticregression"]
    print(f"\n{name} coefficients (per 1 sd):")
    for c, w, mu, sd in zip(cols, lr.coef_[0], sc.mean_, sc.scale_):
        print(f"  {c:20s} {w:+.3f}   (mean {mu:.3f}, sd {sd:.3f})")
    print("  intercept", round(lr.intercept_[0], 3))
