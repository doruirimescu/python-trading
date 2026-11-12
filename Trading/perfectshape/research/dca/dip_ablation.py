"""Where the pessimism strategies' edge comes from: each fold's fitted strategy (research/dca/kelly4_cv.py) scored on
its held-out era as fitted, with the dip term alone (rate penalty off) and with the rate term alone (dip slope 0).

    python research/dca/dip_ablation.py      # adds "ablation" to data_cache/dca/kelly4_cv.pkl
"""
from dataclasses import replace

import pandas as pd

from perfectshape.dca.continuous import ERAS
from perfectshape.dca.frontier import score
from perfectshape.dca.pages import _markets
from perfectshape.dca.rules import Rule

KEYS = ("n", "win", "median", "worst", "dd_vs_dca", "avg_exposure")

if __name__ == "__main__":
    M = _markets()
    path = "data_cache/dca/kelly4_cv.pkl"
    cvs = pd.read_pickle(path)
    for variant in ("combined-pessimism", "combined-pessimism-sells"):
        rows = []
        for fold in cvs[variant]["folds"]:
            k = fold["kelly"]
            parts = {"as fitted": k, "dip only": replace(k, a=0.0), "rates only": replace(k, p_dip=0.0)}
            rules = [Rule(name, v.target, v.sell) for name, v in parts.items()]
            a, b = ERAS[fold["test"]]
            res = score(M["all"], rules, 10, k.account(), a, b, step=3, feats=M["f_all"])
            row = {"test": fold["test"], **{r["rule"]: {x: r[x] for x in KEYS} for r in res}}
            rows.append(row)
            print(variant, fold["test"], {n: f"{r['win']:.0%} {r['median']:+.1%} worst {r['worst']:+.1%} fall "
                                             f"{r['dd_vs_dca'] * 100:+.1f} exp {r['avg_exposure']:.2f}" for n, r in row.items() if n != "test"})
        cvs[variant]["ablation"] = rows
    pd.to_pickle(cvs, path)
