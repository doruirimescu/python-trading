"""Fit the combined (continuous, never-selling) strategy on 1962-1999 and test it where it was not fitted.

    python research/dca/fit_continuous.py      # ~5 min on 16 cores; writes data_cache/dca/combined_fit.pkl

Also fits each seed twice more (different random seeds) to show how stable the fitted function is, and compares
with the rule-based no-sell rules on the same accounts.
"""
import time

import pandas as pd

from perfectshape.dca.continuous import Combined, evaluate_train, fit
from perfectshape.dca.data import load_early_history, load_market
from perfectshape.dca.frontier import score
from perfectshape.dca.rules import Rule, flat, rate_guard, trend, unless
from perfectshape.dca.signals import features

KEYS = ("n", "win", "median", "p10", "worst", "best", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower", "calls", "avg_exposure")


def tests(c: Combined, extra: list[Rule]) -> pd.DataFrame:
    us, early = load_market(), load_early_history()
    fu, fe = features(us), features(early)
    rules = [c.rule()] + extra
    sets = {"train 1962-1999 (10y)": (us, fu, 10, "1962-01-01", "1999-12-31"),
            "TEST 2000-2026 (10y)": (us, fu, 10, "2000-01-01", None),
            "TEST 1928-1961 (10y)": (early, fe, 10, None, None),
            "all 1962-2026 (5y)": (us, fu, 5, None, None), "all 1962-2026 (10y)": (us, fu, 10, None, None),
            "all 1962-2026 (20y)": (us, fu, 20, None, None)}
    rows = []
    for label, (m, f, y, a, b) in sets.items():
        # every rule runs with the combined strategy's caps (debt in payments, cash in payments): same account rules
        for r in score(m, rules, y, c.account(), a, b, step=3, feats=f):
            rows.append({"set": label, "rule": r["rule"], **{k: r[k] for k in KEYS}})
    return pd.DataFrame(rows)


def run_estimated():
    """The robust version: expected-return equation by least squares on 1962-1999, sizing fitted on 1962-1999."""
    from perfectshape.dca.continuous import TRAIN, estimate_expected, fit_sizing

    us = load_market()
    est = estimate_expected(us, features(us), *TRAIN)
    print("expected-return equation, least squares on", est["months"], "months of 1962-1999:")
    print({k: round(est[k], 4) for k in ("p0", "p1", "a", "b")}, "t:", {k: round(v, 2) for k, v in est["t"].items()})
    c, grid = fit_sizing(est)
    g = pd.DataFrame(grid).sort_values("score", ascending=False)
    print("best sizing on 1962-1999 (top 10 of", len(g), "):")
    print(g.head(10).round(4).to_string(index=False))
    return c, est, g


if __name__ == "__main__":
    import sys

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    if "--estimated" in sys.argv:
        c, est, g = run_estimated()
        print("\nchosen:", c)
        g2 = rate_guard()
        extra = [Rule("plain DCA", flat(1.0), False, "dca"),
                 Rule("rule: trend 1.25 + guard, no sell", unless(trend(1.25), g2), False, "rule"),
                 Rule("rule: trend 1.5 + guard, no sell", unless(trend(1.5), g2), False, "rule")]
        d = tests(c, extra)
        for col in ("win", "median", "p10", "worst", "best", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower"):
            d[col] = (d[col] * 100).round(1)
        d["avg_exposure"] = d["avg_exposure"].round(2)
        print(d.to_string(index=False))
        old = pd.read_pickle("data_cache/dca/combined_fit.pkl")
        old.update({"estimated": c, "estimate": est, "sizing_grid": g, "tests_estimated": d})
        pd.to_pickle(old, "data_cache/dca/combined_fit.pkl")
        sys.exit(0)
    fits = []
    for seed in (7, 11, 23):
        t = time.time()
        c, res = fit(seed=seed)
        r = evaluate_train(c)
        print(f"seed {seed}: {c}  train {r}  ({time.time() - t:.0f}s, {res.nfev} evaluations)", flush=True)
        fits.append((seed, c, r))
    best = max(fits, key=lambda x: x[2]["median"] - (0 if x[2]["worst"] >= -0.03 and x[2]["dd"] >= -0.02 else 1))[1]
    print("\nchosen:", best)
    g = rate_guard()
    extra = [Rule("plain DCA", flat(1.0), False, "dca"),
             Rule("rule: trend 1.25 + guard, no sell", unless(trend(1.25), g), False, "rule"),
             Rule("rule: trend 1.5 + guard, no sell", unless(trend(1.5), g), False, "rule"),
             Rule("rule: trend 2.0 + guard, no sell", unless(trend(2.0), g), False, "rule")]
    d = tests(best, extra)
    for c in ("win", "median", "p10", "worst", "best", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower"):
        d[c] = (d[c] * 100).round(1)
    d["avg_exposure"] = d["avg_exposure"].round(2)
    print(d.to_string(index=False))
    pd.to_pickle({"fits": fits, "best": best, "tests": d}, "data_cache/dca/combined_fit.pkl")
