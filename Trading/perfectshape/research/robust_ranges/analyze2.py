"""Rules: success rate of candidates passing threshold rules on a few features, time-split validated."""
import glob
import itertools
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 300)

pat = sys.argv[1] if len(sys.argv) > 1 else "parts/w2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
df["succ"] = ((df.f2_n_closed >= 2) & (df.f2_ret > 0)).astype(int)
df["passed"] = df.score >= 0.6
df["exp_rev2"] = df.is_rev * 504 / df.W          # in-sample reversions per 2 years
df["train"] = df.year <= 2019

FEATS = [c for c in sys.argv[2].split(",")] if len(sys.argv) > 2 else [
    "trades_per_year", "to_mean", "half_life", "band_over_vol", "swings", "cross_per_yr", "pain", "wf2_min_rev",
    "wf2_mean_rev", "wf1_pos", "blk_min_rev", "blk_zero", "med_shift_max", "med_shift_last", "recent_cross",
    "recent_slope", "vol_last_ratio", "nb_mean", "nb_frac", "loo_mean", "loo_min", "leg_corr", "beta_spy_absmax",
    "beta_etf_absmax", "adf_t", "vr250", "half_mid_shift", "score", "harvest", "coverage", "end_dist", "band_pos"]


def rate(d):
    return d.succ.mean() if len(d) else np.nan


def top_per_group(d, n=10, key="score"):
    return d.sort_values(key, ascending=False).groupby("grp").head(n)


print("baseline: all %.3f | passed %.3f | top10/scan by score %.3f | train/test passed %.3f / %.3f" % (
    rate(df), rate(df[df.passed]), rate(top_per_group(df[df.passed])), rate(df[df.passed & df.train]),
    rate(df[df.passed & ~df.train])))

# single-feature quintiles (passed only)
d = df[df.passed]
for f in FEATS:
    try:
        q = pd.qcut(d[f].rank(method="first"), 5, labels=False)
    except ValueError:
        continue
    g = d.groupby(q).agg(lo=(f, "min"), hi=(f, "max"), succ=("succ", "mean"), ret=("f2_ret", "mean"))
    tr = d[d.train].groupby(q[d.train]).succ.mean()
    te = d[~d.train].groupby(q[~d.train]).succ.mean()
    g["succ_train"], g["succ_test"] = tr, te
    print(f"\n{f}\n" + g.round(3).to_string())
