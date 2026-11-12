"""Round 6: the finalists under stress: horizons, the 1928-1961 holdout, costs, margin rate, other markets.

    python research/dca/round6.py
"""
import pandas as pd

from perfectshape.dca.data import load_early_history, load_market, load_other_market
from perfectshape.dca.exposure import ExposureConfig
from perfectshape.dca.frontier import score
from perfectshape.dca.rules import Rule, ladder, rate_guard, switch, trend, unless

g = rate_guard()
L3X = [(-0.10, 0.20), (-0.20, 0.40), (-0.30, 0.60)]
RULES = [
    Rule("crash -10% -> borrow 10% [pay back]", ladder([(-0.10, 0.10)]), False),
    Rule("crash ladder +20/40/60% [sell]", ladder(L3X), True),
    Rule("crash ladder x2 after a bounce (200d) [sell]", ladder(L3X, confirm=200), True),
    Rule("VIX > 30 -> +25% [sell]", switch("vix", 30, 20, 1.25), True),
    Rule("trend 1.25 / 1.0 +guard", unless(trend(1.25), g), True),
    Rule("trend 1.25 / 0.75", trend(1.25, 0.75), True),
    Rule("trend 1.25 / 0.75 +guard", unless(trend(1.25, 0.75), g), True),
    Rule("trend 1.5 / 0.75 +guard", unless(trend(1.5, 0.75), g), True),
    Rule("trend 1.5 / 0.5", trend(1.5, 0.5), True),
    Rule("trend 1.5 / 0.5 +guard", unless(trend(1.5, 0.5), g), True),
    Rule("trend 1.5 / 0.5 +guard, band 1%", unless(trend(1.5, 0.5, band=0.01), g), True),
    Rule("trend 2.0 / 0.5 +guard", unless(trend(2.0, 0.5), g), True),
    Rule("trend 1.0 / 0.5 (no borrowing)", trend(1.0, 0.5), True),
]


def cell(r):
    return (f"{r['win'] * 100:3.0f}% {r['median'] * 100:+5.1f} w{r['worst'] * 100:+6.1f} | dd {r['dd_vs_dca'] * 100:+5.1f} "
            f"w{r['dd_vs_dca_worst'] * 100:+6.1f} ok{r['dd_shallower'] * 100:3.0f}%")


if __name__ == "__main__":
    us, early = load_market(), load_early_history()
    base = ExposureConfig()
    sets = {"US 62-26 10y": (us, 10, base), "US 5y": (us, 5, base), "US 20y": (us, 20, base), "1928-61 10y": (early, 10, base),
            "US 10y costs 20bp": (us, 10, ExposureConfig(trade_cost=0.002)),
            "US 10y margin +2%": (us, 10, ExposureConfig(borrow_spread=0.02)),
            "US 10y from 1990": (us, 10, base)}
    for tk, nm in (("^NDX", "NDX 10y"), ("^GDAXI", "DAX 10y"), ("^N225", "Nikkei 10y"), ("^FTSE", "FTSE 10y")):
        sets[nm] = (load_other_market(tk), 10, base)
    out = {}
    for k, (m, y, cfg) in sets.items():
        rows = score(m, RULES, y, cfg, first="1990-01-01" if "1990" in k else None, step=3)
        out[k] = {r["rule"]: cell(r) for r in rows}
        print(f"{k}: {rows[0]['n']} accounts, DCA deepest fall median {rows[0]['dca_dd_median']:.0%} worst {rows[0]['dca_dd_worst']:.0%}", flush=True)
    pd.set_option("display.width", 400)
    pd.set_option("display.max_colwidth", 60)
    print("win, median edge, worst edge | fall vs DCA (points; + = shallower): median, worst, share of accounts shallower")
    d = pd.DataFrame(out)
    for i in range(0, len(d.columns), 3):
        print(d.iloc[:, i:i + 3].to_string(), "\n")
