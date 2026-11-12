"""Leave-one-era-out test of the combined Kelly strategy (and of the plain trend rules, under the same account caps).

For each era (1928-1961, 1962-1999, 2000-today): estimate the forecast on the two other eras' months, choose the Kelly
fraction and the debt / cash caps on the other eras' 10-year accounts, then score everything on the held-out era.
Finally fit on all eras: the strategy for today.

    python research/dca/kelly_cv.py         # writes data_cache/dca/kelly_cv.pkl
"""
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from perfectshape.dca.continuous import ERAS, Kelly, estimate_kelly_forecast, month_table
from perfectshape.dca.evaluate import windows
from perfectshape.dca.exposure import ExposureConfig, simulate_exposure
from perfectshape.dca.frontier import score
from perfectshape.dca.pages import _markets
from perfectshape.dca.rules import Rule, rate_guard, trend, unless

K_GRID = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6)
DEBT_GRID = (6, 12, 18, 24, 36)
CASH_GRID = (0, 3, 6)
_BASE = {}


def accounts(eras):
    dates = _markets()["all"].index.values.astype("datetime64[D]")
    s, e = [], []
    for era in eras:
        a, b = ERAS[era]
        w = windows(dates, 10, a, b, step=3)
        s.append(w.starts)
        e.append(w.ends)
    return np.concatenate(s), np.concatenate(e)


def _base(eras: tuple):
    if eras not in _BASE:
        m = _markets()["all"]
        s, e = accounts(eras)
        dates = m.index.values.astype("datetime64[D]")
        _BASE[eras] = simulate_exposure(m["tr"].to_numpy(), dates, np.ones(len(dates)), m["y10"].to_numpy(),
                                        m["y3m"].to_numpy(), ExposureConfig(), False, s, e)
    return _BASE[eras]


def judge(edge, dd, calls):
    """The penalised objective of continuous.objective, on any set of accounts."""
    med, worst, ddm, ddw = np.median(edge), edge.min(), np.median(dd), dd.min()
    return float(med - (5 * max(0, -0.03 - worst) + 3 * max(0, -0.02 - ddm) + 2 * max(0, -0.08 - ddw) + 0.05 * calls))


def _eval(job):
    params, eras = job
    M = _markets()
    m, f = M["all"], M["f_all"]
    k = Kelly(**params)
    s, e = accounts(eras)
    dates = m.index.values.astype("datetime64[D]")
    base = _base(tuple(eras))
    res = simulate_exposure(m["tr"].to_numpy(), dates, np.asarray(k.target(f), dtype=float), m["y10"].to_numpy(),
                            m["y3m"].to_numpy(), k.account(), False, s, e)
    edge = res["wealth"] / base["wealth"] - 1.0
    dd = res["max_dd"] - base["max_dd"]
    return params, judge(edge, dd, int(res["margin_calls"].sum())), float(np.median(edge)), float(edge.min())


def fit_on(eras, mon, pool):
    fc = estimate_kelly_forecast(mon, eras)
    jobs = [({"p_above": fc["p_above"], "p_below": fc["p_below"], "a": fc["a"], "k": k, "max_debt": d, "max_cash": c}, list(eras))
            for k in K_GRID for d in DEBT_GRID for c in CASH_GRID]
    res = list(pool.map(_eval, jobs))
    best = max(res, key=lambda r: r[1])
    return Kelly(**best[0]), fc, best


def score_era(rules, era, cfg):
    M = _markets()
    a, b = ERAS[era]
    rows = score(M["all"], rules, 10, cfg, a, b, step=3, feats=M["f_all"])
    keys = ("n", "win", "median", "worst", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower", "calls", "avg_exposure")
    return {r["rule"]: {k: r[k] for k in keys} for r in rows}


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    M = _markets()
    mon = month_table(M["all"], M["f_all"])
    g = rate_guard()
    folds = []
    with ProcessPoolExecutor(14) as pool:
        for test in ERAS:
            train = [e for e in ERAS if e != test]
            kel, fc, best = fit_on(train, mon, pool)
            fcs = {k: round(v, 4) for k, v in fc.items() if k in ("p_above", "p_below", "a")}
            print(f"\n== test {test}, fitted on {train}: forecast {fcs}; sizing k={kel.k} debt {kel.max_debt} cash {kel.max_cash}; "
                  f"train score {best[1]:+.4f} median {best[2]:+.4f} worst {best[3]:+.4f}", flush=True)
            rules = [kel.rule(), Rule("trend 1.25 + guard (no sell)", unless(trend(1.25), g), False),
                     Rule("trend 1.5 + guard (no sell)", unless(trend(1.5), g), False)]
            out = score_era(rules, test, kel.account())        # same caps for all: a like-for-like comparison
            for name, r in out.items():
                print(f"   {name:<62} win {r['win']:.0%}  median {r['median']:+.1%}  worst {r['worst']:+.1%}  fall vs DCA "
                      f"{r['dd_vs_dca'] * 100:+.1f} (worst {r['dd_vs_dca_worst'] * 100:+.1f}, shallower in {r['dd_shallower']:.0%})  "
                      f"calls {r['calls']}  exposure {r['avg_exposure']:.2f}", flush=True)
            folds.append({"test": test, "train": train, "kelly": kel, "forecast": fc, "train_score": best, "results": out})
        final, fc_all, best_all = fit_on(list(ERAS), mon, pool)
    print(f"\n== fitted on all eras: forecast {fc_all}; sizing k={final.k} debt {final.max_debt} cash {final.max_cash}; score {best_all}")
    pd.to_pickle({"folds": folds, "final": final, "forecast_all": fc_all, "best_all": best_all}, "data_cache/dca/kelly_cv.pkl")
