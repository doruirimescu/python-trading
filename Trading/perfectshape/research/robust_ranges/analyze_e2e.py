import glob, sys
import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
pat = sys.argv[1] if len(sys.argv) > 1 else "parts/e2e2520_*.pkl"
df = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)], ignore_index=True)
df["succ"] = ((df.f2_n >= 2) & (df.f2_ret > 0)).astype(int)
df["succ1"] = ((df.f1_n >= 1) & (df.f1_ret > 0)).astype(int)
df["year"] = df["asof"].str[:4].astype(int)
df["grp"] = df.sector + "|" + df["asof"]
scans = df.groupby("robust").grp.nunique()
allscans = pd.concat([pd.read_pickle(f) for f in glob.glob(pat)]).pipe(lambda d: d.sector + d["asof"]).nunique()
print("scans with results (plain / robust):", scans.to_dict())
def summ(d):
    return pd.Series({"listed": len(d), "scans_w_list": d.grp.nunique(), "per_scan": len(d) / max(d.grp.nunique(), 1),
                      "succ_2y": d.succ.mean(), "n2": (d.f2_n >= 2).mean(), "mean_rev_2y": d.f2_n.mean(),
                      "ret_2y": d.f2_ret.mean(), "med_2y": d.f2_ret.median(), "loss>20%": (d.f2_ret < -0.2).mean(),
                      "loss>50%": (d.f2_ret < -0.5).mean(), "succ_1y": d.succ1.mean(), "ret_1y": d.f1_ret.mean()})
print(df.groupby("robust").apply(summ).round(3).T.to_string())
print("\ntop 10 per scan only:")
print(df[df["rank"] <= 10].groupby("robust").apply(summ).round(3).T.to_string())
print("\nby period (scan end <= 2019 / >= 2020):")
print(df.groupby(["robust", df.year >= 2020]).apply(summ)[["listed", "succ_2y", "ret_2y", "med_2y", "loss>20%"]].round(3).to_string())
print("\nby year:")
print(df.groupby(["year", "robust"]).apply(summ)[["listed", "succ_2y", "ret_2y"]].unstack().round(3).to_string())
print("\nby sector:")
print(df.groupby(["sector", "robust"]).apply(summ)[["listed", "succ_2y", "ret_2y"]].unstack().round(3).to_string())
