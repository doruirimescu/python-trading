"""Mega strategy, round 1: does the synthetic leveraged fund match the real ones, and what do the building blocks do?

    python research/dca/mega_explore.py
"""
import numpy as np
import pandas as pd
import yfinance as yf

from perfectshape.dca.mega import ERAS, Mega, assets, dca_stats, leveraged, perf


def real(ticker):
    s = yf.download(ticker, start="2005-01-01", auto_adjust=True, progress=False)["Close"].squeeze().dropna()
    return s.pct_change().dropna()


def line(name, r, a, extra=""):
    p = perf(r, a["bill"])
    cells = []
    for e, (x, y) in ERAS.items():
        q = perf(r, a["bill"], x, y)
        cells.append(f"{q['cagr']:+6.1%}/{q['sharpe']:.2f}/{q['max_dd']:.0%}" if q["n"] else "       -      ")
    d = dca_stats(r.to_numpy(), a["spx"].to_numpy(), a.index.values.astype("datetime64[D]"))
    print(f"{name:<44} {p['cagr']:+6.1%} sh {p['sharpe']:.2f} dd {p['max_dd']:4.0%} | " + " | ".join(cells)
          + f" | dca win {d['win']:.0%} med {d['median']:+.0%} worst {d['worst']:+.0%} {extra}", flush=True)


if __name__ == "__main__":
    a = assets()
    print("assets from", {c: str(a[c].first_valid_index().date()) for c in ("spx", "ndx", "bond", "gold")})
    print("\n== synthetic vs real funds (CAGR over the real fund's life)")
    for ticker, col, lev in (("UPRO", "spx", 3), ("SSO", "spx", 2), ("TQQQ", "ndx", 3), ("TYD", "bond", 3), ("IEF", "bond", 1)):
        rr = real(ticker)
        syn = leveraged(a[col], a["bill"], lev, days=a["days"]).reindex(rr.index).dropna()
        rr = rr.reindex(syn.index)
        yrs = len(rr) / 252
        g = lambda x: (1 + x).prod() ** (1 / yrs) - 1
        print(f"  {ticker:<5} {lev}x {col}: real {g(rr):+.1%}  synthetic {g(syn):+.1%}  daily correlation {np.corrcoef(rr, syn)[0, 1]:.3f}  from {rr.index[0].date()}")
    print("\n== name | all: CAGR, Sharpe, deepest fall | per era CAGR/Sharpe/fall: " + ", ".join(ERAS))
    line("S&P 500 (plain DCA)", a["spx"], a)
    for lev in (2, 3):
        line(f"{lev}x S&P 500, held", leveraged(a["spx"], a["bill"], lev, days=a["days"]), a)
    line("3x 55% S&P / 45% bond, rebalanced daily", 0.55 * leveraged(a["spx"], a["bill"], 3, days=a["days"])
         + 0.45 * leveraged(a["bond"], a["bill"], 3, days=a["days"]), a)
    for lev in (1, 2, 3):
        for vt in (None, 0.25):
            for bl in (1,):
                m = Mega(lev=lev, vol_target=vt, bond_lev=bl)
                r, w = m.returns(a)
                line(f"trend {lev}x, vol target {vt}, safe bond {bl}x", r, a, f"eq {w['eq'].mean():.2f}")
    pd.to_pickle(a, "data_cache/dca/mega_assets_check.pkl")
