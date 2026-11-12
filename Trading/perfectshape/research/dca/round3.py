"""Round 3: two guards on the monthly trend rule, on 1962-2026 and on the 1928-1961 holdout.

* rate guard: do not borrow while the 10-year yield has risen more than x points over the last n days;
* young-account limit: debt at most a share of the position (a stricter initial margin).

    python research/dca/round3.py
"""
import pandas as pd

from perfectshape.dca.account import AccountConfig
from perfectshape.dca.data import load_early_history, load_market, load_other_market
from perfectshape.dca.evaluate import compare
from perfectshape.dca.policy import const, to_array, trend_policy
from perfectshape.dca.signals import features


def guard(x, n):
    return lambda g: (g["y10"] - g["y10"].shift(n)) > x


def line(m, pols, years, cfg=AccountConfig()):
    f = features(m)
    out = compare(m, {"dca": const(0), **pols} and {k: to_array(p, f) for k, p in {"dca": const(0), **pols}.items()}, years, cfg)
    return {k: f"{v['win'] * 100:3.0f}% {v['median'] * 100:+5.2f} {v['p10'] * 100:+5.2f} {v['worst'] * 100:+6.2f} c{v['calls']}" for k, v in out.items()}


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    us, early = load_market(), load_early_history()
    sets = {"S&P 62-26 5y": (us, 5), "S&P 62-26 10y": (us, 10), "S&P 28-61 5y": (early, 5), "S&P 28-61 10y": (early, 10),
            "NDX 10y": (load_other_market("^NDX"), 10), "DAX 10y": (load_other_market("^GDAXI"), 10)}
    pols = {"trend monthly": trend_policy(200, monthly=True)}
    for n in (63, 126, 252):
        for x in (0.4, 0.6, 0.8, 1.0):
            pols[f"guard +{x} in {n}d"] = trend_policy(200, monthly=True, veto=guard(x, n))
    print("rate guard: win, median, p10, worst (% of final wealth), margin calls")
    print(pd.DataFrame({k: line(m, pols, y) for k, (m, y) in sets.items()}).to_string())
    print("\nyoung-account limit (debt <= share of position), trend monthly and with guard +0.6/126d")
    pols = {"trend monthly": trend_policy(200, monthly=True), "trend + guard": trend_policy(200, monthly=True, veto=guard(0.6, 126)),
            "early 6": const(-6)}
    for im, lab in ((0.5, "debt <= 50% of position (Reg T)"), (0.75, "debt <= 25%"), (0.85, "debt <= 15%"), (0.9, "debt <= 10%"), (0.95, "debt <= 5%")):
        print(f"\n{lab}")
        print(pd.DataFrame({k: line(m, pols, y, AccountConfig(initial_margin=im)) for k, (m, y) in sets.items()}).to_string())
