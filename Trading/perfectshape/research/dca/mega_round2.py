"""Mega strategy, round 2: trend-following risk parity with leverage, and how fragile each choice is.

    python research/dca/mega_round2.py
"""
import sys

from perfectshape.dca.mega import ERAS, Mega, Parity, assets, dca_stats, perf


def line(name, r, a, extra=""):
    p = perf(r, a["bill"])
    cells = []
    for e, (x, y) in ERAS.items():
        q = perf(r, a["bill"], x, y)
        cells.append(f"{q['cagr']:+6.1%}/{q['sharpe']:.2f}/{q['max_dd']:.0%}" if q["n"] else "       -      ")
    d = dca_stats(r.to_numpy(), a["spx"].to_numpy(), a.index.values.astype("datetime64[D]"))
    print(f"{name:<46} {p['cagr']:+6.1%} sh {p['sharpe']:.2f} dd {p['max_dd']:4.0%} | " + " | ".join(cells)
          + f" | win {d['win']:.0%} med {d['median']:+.0%} worst {d['worst']:+.0%} {extra}", flush=True)


if __name__ == "__main__":
    a = assets()
    line("S&P 500 (plain DCA)", a["spx"], a)
    line("trend 3x, vol target 25%", Mega().returns(a)[0], a)
    base = Parity()
    variants = {"parity base (15% vol, 3x cap)": base}
    for t in (0.10, 0.20, 0.25, 0.30):
        variants[f"target {t:.0%}"] = Parity(target=t)
    for ma in (100, 150, 250):
        variants[f"ma {ma}"] = Parity(ma=ma)
    for vd in (21, 126):
        variants[f"vol days {vd}"] = Parity(vol_days=vd)
    variants["no band"] = Parity(band=0.0)
    variants["band 2%"] = Parity(band=0.02)
    variants["risk 60/40/0 (no gold)"] = Parity(risk=(0.6, 0.4, 0.0))
    variants["risk 1/0/0 (stocks only)"] = Parity(risk=(1.0, 0.0, 0.0))
    variants["risk 1/3 each"] = Parity(risk=(1 / 3, 1 / 3, 1 / 3))
    variants["cap 2x"] = Parity(max_gross=2.0)
    variants["cap 1x (no leverage)"] = Parity(max_gross=1.0)
    variants["ndx half of stocks"] = Parity(ndx=0.5)
    variants["ndx all of stocks"] = Parity(ndx=1.0)
    variants["target 20%, ndx half"] = Parity(target=0.20, ndx=0.5)
    variants["cost 0.3%, spread 1.5%"] = Parity(cost=0.003, spread=0.015)
    variants["lag 3 days"] = Parity(lag=3)
    only = sys.argv[1:]
    for name, v in variants.items():
        if only and not any(o in name for o in only):
            continue
        r, w = v.returns(a)
        line(name, r, a, f"gross {w.sum(axis=1).mean():.2f}")
