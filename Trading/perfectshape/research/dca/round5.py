"""Round 5: the family that can beat plain DCA *and* fall less: borrowed above the 200-day average, partly in cash
below it. Grid over the two exposures, the rate guard, how often it decides, and a volatility cap on the borrowing;
scored on 1962-2026 (10- and 20-year accounts) and on the 1928-1961 holdout.

    python research/dca/round5.py            # writes data_cache/dca/r5.pkl and prints the frontier
"""
import pandas as pd

from perfectshape.dca.data import load_early_history, load_market
from perfectshape.dca.exposure import ExposureConfig
from perfectshape.dca.frontier import score
from perfectshape.dca.rules import Rule, only_if, rate_guard, trend, unless, vol_target
from perfectshape.dca.signals import features


def grid() -> list[Rule]:
    R = []
    g = rate_guard()
    for up in (1.25, 1.5, 2.0):
        for down in (1.0, 0.75, 0.5, 0.25, 0.0):
            for timing, kw in (("daily", {}), ("band 1%", {"band": 0.01}), ("monthly", {"monthly": True})):
                base = trend(up, down, **kw)
                R.append(Rule(f"{up:.2f}/{down:.2f} {timing}", base, True, "trend"))
                R.append(Rule(f"{up:.2f}/{down:.2f} {timing} +guard", unless(base, g), True, "guard"))
            # borrowing scaled down when volatility is high: above the average min(up, 15 / vol), never under 1
            vt = lambda f, up=up, down=down: (only_if(vol_target(15, 1.0, up), lambda q: q["trend"] > 0)(f)
                                               + trend(1.0, down, monthly=True)(f) - 1.0)
            R.append(Rule(f"{up:.2f}/{down:.2f} monthly volcap", vt, True, "volcap"))
            R.append(Rule(f"{up:.2f}/{down:.2f} monthly volcap +guard", unless(vt, g), True, "volcap+guard"))
    return R


if __name__ == "__main__":
    us, early = load_market(), load_early_history()
    fu, fe = features(us), features(early)
    rules = grid()
    cfg = ExposureConfig()
    sets = {"us10": score(us, rules, 10, cfg, step=3, feats=fu), "us20": score(us, rules, 20, cfg, step=6, feats=fu),
            "us5": score(us, rules, 5, cfg, step=3, feats=fu), "early10": score(early, rules, 10, cfg, step=3, feats=fe)}
    pd.to_pickle(sets, "data_cache/dca/r5.pkl")
    keep = ("win", "median", "p10", "worst", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower", "turnover", "avg_exposure")
    d = pd.DataFrame({rules[i].name: {f"{k} {c}": rows[i][c] for k, rows in sets.items() for c in keep}
                      for i in range(len(rules))}).T
    pd.set_option("display.width", 300)
    pd.set_option("display.max_rows", 400)
    pct = [c for c in d.columns if not c.endswith(("turnover", "avg_exposure"))]
    d[pct] = (d[pct] * 100).round(1)
    d = d.round(2)
    cols = ["us10 win", "us10 median", "us10 worst", "us10 dd_vs_dca", "us10 dd_vs_dca_worst", "us10 dd_shallower", "us10 turnover",
            "us20 win", "us20 median", "us20 worst", "us5 win", "us5 worst", "early10 win", "early10 median", "early10 worst",
            "early10 dd_vs_dca", "early10 dd_shallower"]
    print("all rules sell to rebalance. Sorted by the median 10-year edge on 1962-2026.")
    print(d[cols].sort_values("us10 median", ascending=False).to_string())
    ok = d[(d["us10 dd_shallower"] >= 90) & (d["early10 dd_shallower"] >= 90) & (d["us10 win"] >= 85) & (d["early10 win"] >= 85)]
    print("\n== beats DCA in >= 85% of accounts and falls less in >= 90%, in both 1962-2026 and 1928-1961:")
    print(ok[cols].sort_values("us10 median", ascending=False).to_string())
