"""Round 4: borrowing sized against the account. Crash ladders, trend, VIX, volatility, news, credit, guards and
combinations, each scored on its edge over plain DCA and on its drawdown against plain DCA's.

    python research/dca/round4.py [--years 10] [--first 1962-01-01] [--step 3] [--set all] [--market us|early|^N225]
"""
import argparse

import pandas as pd

from perfectshape.dca.data import load_early_history, load_market, load_other_market
from perfectshape.dca.exposure import ExposureConfig
from perfectshape.dca.frontier import score
from perfectshape.dca.rules import Rule, both, flat, highest, ladder, only_if, rate_guard, switch, trend, unless, vol_target

L10 = [(-0.10, 0.10)]
L3 = [(-0.10, 0.10), (-0.20, 0.20), (-0.30, 0.30)]
L3X = [(-0.10, 0.20), (-0.20, 0.40), (-0.30, 0.60)]
DEEP = [(-0.20, 0.25), (-0.30, 0.50), (-0.40, 0.75)]


def rules() -> list[Rule]:
    R = []

    def add(name, e, family, sells=(False, True)):
        for s in sells:
            R.append(Rule(f"{name} [{'sell' if s else 'pay'}]", e, s, family))

    for x in (1.1, 1.25, 1.5, 2.0):
        add(f"always {x:.2f}", flat(x), "always", (True,))
    add("crash -10% -> +10%", ladder(L10), "crash")
    add("crash -10/-20/-30% -> +10/20/30%", ladder(L3), "crash")
    add("crash -10/-20/-30% -> +20/40/60%", ladder(L3X), "crash")
    add("crash -20/-30/-40% -> +25/50/75%", ladder(DEEP), "crash")
    add("crash -20% -> +50%", ladder([(-0.20, 0.50)]), "crash")
    add("crash -30% -> +100%", ladder([(-0.30, 1.0)]), "crash")
    add("crash ladder x1, wait for a bounce (50d)", ladder(L3, confirm=50), "crash")
    add("crash ladder x2, wait for a bounce (50d)", ladder(L3X, confirm=50), "crash")
    add("crash ladder x2, bounce (200d)", ladder(L3X, confirm=200), "crash")
    add("crash ladder x2, held until new high -0%", ladder(L3X, exit=-0.001), "crash")
    add("crash ladder x2, 1y-high drawdown", ladder(L3X, col="dd"), "crash")
    for x in (1.1, 1.25, 1.5, 2.0):
        add(f"trend {x:.2f} / 1.0", trend(x), "trend")
    add("trend 1.25 / 1.0 monthly", trend(1.25, monthly=True), "trend")
    add("trend 1.5 / 1.0 monthly", trend(1.5, monthly=True), "trend")
    add("trend 1.0 / 0.5", trend(1.0, 0.5), "trend+cash", (True,))
    add("trend 1.0 / 0.0", trend(1.0, 0.0), "trend+cash", (True,))
    add("trend 1.25 / 0.75", trend(1.25, 0.75), "trend+cash", (True,))
    add("trend 1.5 / 0.5", trend(1.5, 0.5), "trend+cash", (True,))
    add("trend 1.5 / 0.5, 2% band", trend(1.5, 0.5, band=0.02), "trend+cash", (True,))
    add("trend 2.0 / 0.0", trend(2.0, 0.0), "trend+cash", (True,))
    add("VIX > 30 -> +25% (until < 20)", switch("vix", 30, 20, 1.25), "vix")
    add("VIX > 30 -> +50% (until < 20)", switch("vix", 30, 20, 1.5), "vix")
    add("VIX > 40 -> +50% (until < 20)", switch("vix", 40, 20, 1.5), "vix")
    add("VIX > 40 -> +100% (until < 25)", switch("vix", 40, 25, 2.0), "vix")
    add("VIX top 10% of 5y -> +50%", switch("vix_pct", 0.9, 0.5, 1.5), "vix")
    add("VIX < 15 -> +50% (until > 20)", switch("vix", 15, 20, 1.5), "vix")
    add("VIX term inverted -> +50%", switch("term", 1.0, 0.92, 1.5), "vix")
    add("vol spike (1.5x usual) -> +25%", switch("rv_ratio", 1.5, 1.0, 1.25), "vol")
    add("vol spike (2x usual) -> +50%", switch("rv_ratio", 2.0, 1.0, 1.5), "vol")
    add("realised vol > 30 -> +50%", switch("rv21", 30, 15, 1.5), "vol")
    add("calm (vol < 0.8x usual) -> +50%", switch("rv_ratio", 0.8, 1.2, 1.5), "vol")
    add("vol target 15, 1.0-1.5", vol_target(15, 1.0, 1.5), "vol", (True,))
    add("vol target 15, 1.0-2.0", vol_target(15, 1.0, 2.0), "vol", (True,))
    add("vol target 12, 0.5-1.5", vol_target(12, 0.5, 1.5), "vol+cash", (True,))
    add("vol target 15, 0.5-2.0", vol_target(15, 0.5, 2.0), "vol+cash", (True,))
    add("policy news 1.5x usual -> +25%", switch("epu", 1.5, 1.0, 1.25), "news")
    add("policy news 2x usual -> +50%", switch("epu", 2.0, 1.2, 1.5), "news")
    add("credit rising (HY 3m > +3%) -> +50%", switch("hy_ret63", 0.03, 0.0, 1.5), "credit")
    add("credit falling (HY 3m < -3%) -> +50%", switch("hy_ret63", -0.03, 0.01, 1.5), "credit")
    add("yields falling (6m < -0.5) -> +50%", switch("y10_chg", -0.5, 0.0, 1.5), "rates")
    # combinations
    g = rate_guard()
    add("trend 1.25 + rate guard", unless(trend(1.25), g), "combo")
    add("trend 1.5 + rate guard", unless(trend(1.5), g), "combo")
    add("trend 2.0 + rate guard", unless(trend(2.0), g), "combo")
    add("trend 1.5/0.5 + rate guard", unless(trend(1.5, 0.5), g), "combo+cash", (True,))
    add("trend 1.25 or crash ladder x1", highest(trend(1.25), ladder(L3)), "combo")
    add("trend 1.25 or crash ladder x2", highest(trend(1.25), ladder(L3X)), "combo")
    add("trend 1.5 or crash ladder x2 w/ bounce", highest(trend(1.5), ladder(L3X, confirm=50)), "combo")
    add("trend 1.25 + VIX>30 +25%", both(trend(1.25), switch("vix", 30, 20, 1.25)), "combo")
    add("crash ladder x2 only above 200d", only_if(ladder(L3X, exit=-0.001), lambda q: q["trend"] > 0), "combo")
    add("crash ladder x2 + rate guard", unless(ladder(L3X), g), "combo")
    add("trend 1.5 x vol target (1.0-1.5 only above 200d)", only_if(vol_target(15, 1.0, 1.5), lambda q: q["trend"] > 0), "combo")
    add("trend 2.0 x vol target (1.0-2.0 only above 200d)", only_if(vol_target(15, 1.0, 2.0), lambda q: q["trend"] > 0), "combo")
    add("trend/cash 0.5 below, vol target 1.0-1.5 above",
        lambda f: only_if(vol_target(15, 1.0, 1.5), lambda q: q["trend"] > 0)(f) + trend(1.0, 0.5)(f) - 1.0, "combo+cash", (True,))
    return R


def show(rows, sort="median", top=None):
    d = pd.DataFrame([{k: v for k, v in r.items() if k not in ("edges", "dds", "start_dates")} for r in rows])
    for c in ("win", "median", "p10", "worst", "best", "dd_median", "dd_worst", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower"):
        d[c] = (d[c] * 100).round(1)
    d["avg_exposure"] = d["avg_exposure"].round(2)
    d["turnover"] = d["turnover"].round(2)
    cols = ["rule", "win", "median", "p10", "worst", "best", "dd_median", "dd_worst", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower",
            "calls", "wiped", "avg_exposure", "turnover"]
    d = d.sort_values(sort, ascending=False)
    return d[cols].head(top).to_string(index=False) if top else d[cols].to_string(index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--first", default=None)
    ap.add_argument("--last", default=None)
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--market", default="us")
    ap.add_argument("--family", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    m = load_market() if a.market == "us" else load_early_history() if a.market == "early" else load_other_market(a.market)
    rs = [r for r in rules() if not a.family or r.family.startswith(a.family)]
    rows = score(m, rs, a.years, ExposureConfig(), a.first, a.last, a.step)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_rows", 500)
    print(f"{a.market}: {a.years}-year accounts from {a.first or 'the start'}, {rows[0]['n']} start months; plain DCA's deepest fall: "
          f"median {rows[0]['dca_dd_median']:.1%}, worst {rows[0]['dca_dd_worst']:.1%}")
    print("edge columns: % of final wealth over plain DCA; dd columns: deepest fall of the account, and against plain DCA's (negative = deeper)")
    print(show(rows))
    if a.out:
        pd.to_pickle(rows, a.out)
