"""Mega strategy, round 3: the leveraged trend rule's knobs, one at a time, and volatility management without a trend.

    python research/dca/mega_round3.py
"""
import numpy as np

from mega_round2 import line
from perfectshape.dca.mega import Mega, assets, leveraged

if __name__ == "__main__":
    a = assets()
    line("S&P 500 (plain DCA)", a["spx"], a)
    base = Mega()
    V = {"base: 3x, 200d, band 1%, vol 25%": base}
    for vt in (0.15, 0.20, 0.30, 0.40):
        V[f"vol target {vt:.0%}"] = Mega(vol_target=vt)
    for ma in (100, 150, 250):
        V[f"ma {ma}"] = Mega(ma=ma)
    V["band 0"] = Mega(band=0.0)
    V["band 2%"] = Mega(band=0.02)
    V["band 3%"] = Mega(band=0.03)
    V["vol days 63"] = Mega(vol_days=63)
    V["2x, vol 25%"] = Mega(lev=2)
    V["ndx half"] = Mega(ndx=0.5)
    V["ndx all"] = Mega(ndx=1.0)
    V["no gold"] = Mega(gold=False)
    V["rate guard 0.6"] = Mega(guard=0.6)
    V["bond 3x as the safe asset"] = Mega(bond_lev=3)
    V["risk-off keeps 50% in the S&P"] = Mega(off_equity=0.5)
    V["risk-off stays 100% in the S&P"] = Mega(off_equity=1.0)
    V["lag 3 days"] = Mega(lag=3)
    V["cost 0.3%"] = Mega(cost=0.003)
    for name, v in V.items():
        r, w = v.returns(a)
        line(name, r, a, f"eq {w['eq'].mean():.2f}")
    # no trend at all: exposure = target / volatility, between 0 and 3
    rv = (np.log(a["px"]).diff().rolling(21).std() * np.sqrt(252)).shift(2)
    for t in (0.15, 0.20, 0.25):
        e = (t / rv).clip(upper=3.0).fillna(0.0)
        lev = (e - 1).clip(lower=0)
        r = e * a["spx"] + (1 - e).clip(lower=0) * a["bill"] - lev * (a["bill"] + 0.005 * a["days"] / 365) - lev / 2 * 0.0095 * a["days"] / 365
        line(f"no trend: exposure = {t:.0%} / volatility, max 3x", r, a, f"e {e.mean():.2f}")
    # ensemble of averages: a quarter in each of four trend lengths
    rs = [Mega(ma=m).returns(a)[0] for m in (100, 150, 200, 250)]
    line("ensemble 100/150/200/250", sum(rs) / 4, a)
    rs = [Mega(ma=m, ndx=0.5).returns(a)[0] for m in (100, 150, 200, 250)]
    line("ensemble, ndx half", sum(rs) / 4, a)
    line("3x S&P held", leveraged(a["spx"], a["bill"], 3, days=a["days"]), a)
