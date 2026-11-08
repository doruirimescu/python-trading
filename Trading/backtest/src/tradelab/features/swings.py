"""Fractal swings with explicit confirmation lag.

A swing high at bar i (strictly greater high than the k bars on each side) can only be KNOWN once bar
i+k has closed, so it is stamped at i+k ("confirmed"). Everything exposed here is indexed at the
confirmation bar; ``*_pos`` columns hold the positional index of the pivot bar itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def confirmed_swings(high: pd.Series, low: pd.Series, k: int = 2) -> pd.DataFrame:
    h = high.to_numpy(float)
    l = low.to_numpy(float)
    n = len(h)
    sh_new = np.zeros(n, bool)
    sl_new = np.zeros(n, bool)
    if n > 2 * k:
        w = 2 * k + 1
        from numpy.lib.stride_tricks import sliding_window_view

        hw = sliding_window_view(h, w)
        lw = sliding_window_view(l, w)
        mid_h = hw[:, k]
        mid_l = lw[:, k]
        others_h = np.delete(hw, k, axis=1)
        others_l = np.delete(lw, k, axis=1)
        is_h = (mid_h > others_h.max(axis=1))
        is_l = (mid_l < others_l.min(axis=1))
        # window j covers bars j..j+2k, pivot j+k, confirmed at j+2k
        sh_new[2 * k:] = is_h
        sl_new[2 * k:] = is_l
    pos = np.arange(n)
    piv_pos = pos - k
    last_h = np.full(n, np.nan)
    last_hp = np.full(n, np.nan)
    prev_h = np.full(n, np.nan)
    last_l = np.full(n, np.nan)
    last_lp = np.full(n, np.nan)
    prev_l = np.full(n, np.nan)
    ch = cl = np.nan
    chp = clp = np.nan
    ph = pl = np.nan
    for i in range(n):
        if sh_new[i]:
            ph, ch, chp = ch, h[i - k], i - k
        if sl_new[i]:
            pl, cl, clp = cl, l[i - k], i - k
        last_h[i], last_hp[i], prev_h[i] = ch, chp, ph
        last_l[i], last_lp[i], prev_l[i] = cl, clp, pl
    return pd.DataFrame(
        {
            "swing_high_new": sh_new, "swing_low_new": sl_new,
            "last_swing_high": last_h, "last_swing_high_pos": last_hp, "prev_swing_high": prev_h,
            "last_swing_low": last_l, "last_swing_low_pos": last_lp, "prev_swing_low": prev_l,
        },
        index=high.index,
    )


def market_structure(sw: pd.DataFrame) -> pd.Series:
    """+1 value-up (HH & HL), -1 value-down (LH & LL), 0 otherwise, from confirmed swings."""
    hh = sw["last_swing_high"] > sw["prev_swing_high"]
    hl = sw["last_swing_low"] > sw["prev_swing_low"]
    lh = sw["last_swing_high"] < sw["prev_swing_high"]
    ll = sw["last_swing_low"] < sw["prev_swing_low"]
    out = pd.Series(0, index=sw.index)
    out[hh & hl] = 1
    out[lh & ll] = -1
    return out
