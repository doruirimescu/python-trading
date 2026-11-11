"""Tighter robust-range thresholds, and does passing a gate with room to spare matter? Needs concentration.py output."""
from pathlib import Path

import numpy as np
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
H = str(Path(__file__).resolve().parent) + "/"
for tag in ("w2520", "w1260"):
    d = pd.read_pickle(H + f"{tag}_conc.pkl")
    d = d[d.score >= 0.6].copy()
    d["year"] = d["asof"].str[:4].astype(int)
    d["grp"] = d["sector"] + d["asof"]
    d["succ"] = ((d.f2_n_closed >= 2) & (d.f2_ret > 0)).astype(int)
    d["bad"] = (d.f2_ret < -0.2).astype(int)
    print(f"\n######## {tag}")

    def rule(tpy, bv, rv):
        s = d[(d.trades_per_year >= tpy) & (d.band_over_vol <= bv) & (d.vol_last_ratio >= rv)]
        tr, te = s[s.year <= 2019], s[s.year >= 2020]
        # scan-weighted: mean over scans of the scan's success rate (a dashboard user sees one scan at a time)
        sw = s.groupby("grp").succ.mean()
        return {"tpy": tpy, "bvol": bv, "rvol": rv, "n": len(s), "scans": s.grp.nunique(), "succ": s.succ.mean(),
                "succ_scanw": sw.mean(), "bad": s.bad.mean(), "ret": s.f2_ret.mean(), "med": s.f2_ret.median(),
                "succ_tr": tr.succ.mean(), "succ_te": te.succ.mean(), "bad_tr": tr.bad.mean(), "bad_te": te.bad.mean()}
    rows = [rule(t, b, r) for t in (1.5, 2.0, 2.5) for b in (0.45, 0.4, 0.35) for r in (1.0, 1.1, 1.2)]
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    s = d[(d.trades_per_year >= 1.5) & (d.band_over_vol <= 0.45) & (d.vol_last_ratio >= 1.0)].copy()
    # margin: how far inside each gate, in units of the gate
    s["m_tpy"] = s.trades_per_year / 1.5 - 1
    s["m_bv"] = 1 - s.band_over_vol / 0.45
    s["m_rv"] = s.vol_last_ratio - 1.0
    s["m_min"] = s[["m_tpy", "m_bv", "m_rv"]].min(1)
    for f in ("m_tpy", "m_bv", "m_rv", "m_min"):
        q = pd.qcut(s[f].rank(method="first"), 4, labels=False)
        t = s.groupby(q).agg(lo=(f, "min"), hi=(f, "max"), n=("succ", "size"), succ=("succ", "mean"), bad=("bad", "mean"),
                             ret=("f2_ret", "mean"))
        t["succ_tr"] = s[s.year <= 2019].groupby(q[s.year <= 2019]).succ.mean()
        t["succ_te"] = s[s.year >= 2020].groupby(q[s.year >= 2020]).succ.mean()
        print(f"\n{tag} robust, quartiles of {f}\n{t.round(3).to_string()}")
