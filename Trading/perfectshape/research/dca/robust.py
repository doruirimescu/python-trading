"""Robustness of the finalists: horizons, margin-rate spreads, 1928-1961, other markets.

    python research/dca/robust.py
"""
import pandas as pd

from perfectshape.dca.account import AccountConfig
from perfectshape.dca.data import load_early_history, load_market, load_other_market
from perfectshape.dca.evaluate import compare
from perfectshape.dca.policy import const, to_array, trend_policy, turn_of_month
from perfectshape.dca.signals import features

P = {
    "dca": const(0),
    "early 6": const(-6),
    "tom": turn_of_month(4),
    "trend daily": trend_policy(200),
    "trend monthly": trend_policy(200, monthly=True),
    "trend monthly, off hold 3": trend_policy(200, monthly=True, off=3),
    "trend monthly, yield veto": trend_policy(200, monthly=True, veto=lambda g: g["y10_chg"] > 0.6),
    "trend monthly -5 + tom": trend_policy(200, monthly=True, on=-5, tom=1),
}


def table(m, years, cfg=AccountConfig(), first=None, last=None):
    f = features(m)
    out = compare(m, {k: to_array(p, f) for k, p in P.items()}, years, cfg, first, last)
    return pd.DataFrame({k: {"n": v["n"], "win%": round(v["win"] * 100), "median%": round(v["median"] * 100, 2),
                             "p10%": round(v["p10"] * 100, 2), "worst%": round(v["worst"] * 100, 2), "best%": round(v["best"] * 100, 2),
                             "calls": v["calls"]} for k, v in out.items()}).T


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    m = load_market()
    for y in (5, 20, 30):
        print(f"\n== S&P 500 1962-2026, {y}-year accounts\n{table(m, y).to_string()}")
    for sp in (0.01, 0.02, 0.03):
        print(f"\n== 10-year accounts, margin rate = 10-year yield + {sp:.0%}\n{table(m, 10, AccountConfig(borrow_spread=sp)).to_string()}")
    print(f"\n== 10-year accounts, cash earns nothing\n{table(m, 10, AccountConfig(cash_earns=False)).to_string()}")
    e = load_early_history()
    print(f"\n== S&P 1928-1961 ({e.index[0].date()} .. {e.index[-1].date()}), 10-year accounts\n{table(e, 10).to_string()}")
    print(f"\n== S&P 1928-1961, 5-year accounts\n{table(e, 5).to_string()}")
    for tk, name in [("^NDX", "Nasdaq-100 (price)"), ("^RUT", "Russell 2000 (price)"), ("^GDAXI", "DAX (total return)"),
                     ("^N225", "Nikkei 225 (price)"), ("^FTSE", "FTSE 100 (price)"), ("^HSI", "Hang Seng (price)"),
                     ("^STOXX50E", "Euro Stoxx 50 (price)")]:
        try:
            o = load_other_market(tk)
            print(f"\n== {name} {o.index[0].date()} .. {o.index[-1].date()}, 10-year accounts, US rates\n{table(o, 10).to_string()}")
        except Exception as ex:
            print(f"\n== {name}: failed ({ex})")
