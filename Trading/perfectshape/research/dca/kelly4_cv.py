"""Leave-one-era-out test of the four combined strategies (research/dca/kelly_cv.py, generalised):

    optimism  (trend forecast, VIX volatility)       x  never sells / sells
    pessimism (drawdown forecast, 10-year volatility) x  never sells / sells

For each variant and each era (1928-1961, 1962-1999, 2000-today): estimate the forecast on the two other eras' months,
choose the Kelly fraction and the caps on the other eras' 10-year accounts, then score it on the held-out era next to
two simple rules with the same caps and the same selling: the trend rule and the crash ladder. Finally fit on all eras.

    python research/dca/kelly4_cv.py [variant ...]   # ~30 min on 16 cores; writes data_cache/dca/kelly4_cv.pkl
"""
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from perfectshape.dca.continuous import ERAS, VARIANTS, Kelly, estimate_dip_forecast, estimate_kelly_forecast, month_table
from perfectshape.dca.evaluate import windows
from perfectshape.dca.exposure import ExposureConfig, simulate_exposure
from perfectshape.dca.frontier import score
from perfectshape.dca.pages import _markets
from perfectshape.dca.rules import Rule, ladder, rate_guard, trend, unless

# Kelly fractions: the optimism function at 1 is already ~2x invested (k small); with selling it needs k near full
# Kelly to stay invested at all; the pessimism overlay bets on a small extra return (k large)
K_GRIDS = {("trend", False): (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6), ("trend", True): (0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25),
           ("dip", False): (0.02, 0.035, 0.05, 0.1, 0.15, 0.25, 0.5), ("dip", True): (0.05, 0.1, 0.15, 0.25, 0.5, 1.0, 2.0)}
DEBT_NO_SELL = (6, 12, 18, 24, 36)
CASH_NO_SELL = (0, 3, 6)
DEBT_SELL = (6, 12, 24, 36, float("inf"))
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
                            m["y3m"].to_numpy(), k.account(), k.sell, s, e)
    edge = res["wealth"] / base["wealth"] - 1.0
    dd = res["max_dd"] - base["max_dd"]
    return params, judge(edge, dd, int(res["margin_calls"].sum())), float(np.median(edge)), float(edge.min())


def forecast(signal, mon, eras):
    if signal == "dip":
        fc = estimate_dip_forecast(mon, eras)
        return fc, {"p0": fc["p0"], "p_dip": fc["p_dip"], "a": fc["a"], "dip_cap": fc["cap"], "d_mean": fc["d_mean"]}
    fc = estimate_kelly_forecast(mon, eras)
    return fc, {"p_above": fc["p_above"], "p_below": fc["p_below"], "a": fc["a"]}


def fit_on(variant, eras, mon, pool):
    signal, vol, sell = VARIANTS[variant]
    fc, fp = forecast(signal, mon, eras)
    sizes = ([(d, 0) for d in DEBT_SELL] if sell else [(d, c) for d in DEBT_NO_SELL for c in CASH_NO_SELL])
    jobs = [({**fp, "signal": signal, "vol": vol, "sell": sell, "k": k, "max_debt": d, "max_cash": c}, list(eras))
            for k in K_GRIDS[(signal, sell)] for d, c in sizes]
    res = list(pool.map(_eval, jobs))
    best = max(res, key=lambda r: r[1])
    return Kelly(**best[0]), fc, best


def comparators(sell: bool):
    g = rate_guard()
    if sell:
        return [Rule("Trend 1.5 / 0.5 + guard", unless(trend(1.5, 0.5), g), True),
                Rule("Crash ladder 10 / 20 / 30%", ladder([(-0.10, 0.10), (-0.20, 0.20), (-0.30, 0.30)]), True)]
    return [Rule("Trend 1.25 + guard", unless(trend(1.25), g), False),
            Rule("Crash ladder 10 / 20 / 30%", ladder([(-0.10, 0.10), (-0.20, 0.20), (-0.30, 0.30)]), False)]


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
    import sys
    from pathlib import Path

    only = sys.argv[1:] or list(VARIANTS)          # variants to (re)run; the others are kept from the last run
    path = Path("data_cache/dca/kelly4_cv.pkl")
    out = pd.read_pickle(path) if path.exists() else {}
    with ProcessPoolExecutor(14) as pool:
        for variant, (signal, vol, sell) in VARIANTS.items():
            if variant not in only:
                continue
            folds = []
            for test in ERAS:
                train = [e for e in ERAS if e != test]
                kel, fc, best = fit_on(variant, train, mon, pool)
                fcs = {k: round(v, 4) for k, v in fc.items() if isinstance(v, float)}
                print(f"\n== {variant}: test {test}, fitted on {train}: forecast {fcs}; k={kel.k} debt {kel.max_debt} "
                      f"cash {kel.max_cash}; train score {best[1]:+.4f} median {best[2]:+.4f} worst {best[3]:+.4f}", flush=True)
                res = score_era([kel.rule()] + comparators(sell), test, kel.account())
                for name, r in res.items():
                    print(f"   {name:<62} win {r['win']:.0%}  median {r['median']:+.1%}  worst {r['worst']:+.1%}  fall vs DCA "
                          f"{r['dd_vs_dca'] * 100:+.1f} (worst {r['dd_vs_dca_worst'] * 100:+.1f}, shallower in "
                          f"{r['dd_shallower']:.0%})  calls {r['calls']}  exposure {r['avg_exposure']:.2f}", flush=True)
                folds.append({"test": test, "train": train, "kelly": kel, "forecast": fc, "train_score": best, "results": res})
            final, fc_all, best_all = fit_on(variant, list(ERAS), mon, pool)
            print(f"\n== {variant} fitted on all eras: {final}; score {best_all[1:]}", flush=True)
            out[variant] = {"folds": folds, "final": final, "forecast_all": fc_all, "best_all": best_all}
            pd.to_pickle({v: out[v] for v in VARIANTS if v in out}, path)
