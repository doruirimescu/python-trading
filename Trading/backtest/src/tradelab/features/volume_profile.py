"""Volume profile, value area (VAH/VAL/POC), prior-session joins and developing profile.

Bars' volume is spread uniformly over the tick buckets between low and high (when tick_size > 0),
else over ``n_buckets`` equal-width buckets of the session range.  Value area expands from POC one
bucket at a time towards the larger neighbour (ties -> upper) until >= va_pct of volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _bucketise(lo, hi, tick):
    return int(round(lo / tick)), int(round(hi / tick))


def profile_levels(prices_lo: np.ndarray, prices_hi: np.ndarray, vol: np.ndarray, tick: float, va_pct: float = 0.7):
    """Return (poc, vah, val) for a set of bars. Prices on tick grid expected."""
    if len(vol) == 0 or np.nansum(vol) <= 0:
        return np.nan, np.nan, np.nan
    lo_b = np.round(prices_lo / tick).astype(int)
    hi_b = np.round(prices_hi / tick).astype(int)
    base = lo_b.min()
    nb = hi_b.max() - base + 1
    hist = np.zeros(nb)
    for a, b, v in zip(lo_b - base, hi_b - base, vol):
        hist[a:b + 1] += v / (b - a + 1)
    return _va_from_hist(hist, base, tick, va_pct)


def _va_from_hist(hist: np.ndarray, base: int, tick: float, va_pct: float):
    total = hist.sum()
    if total <= 0:
        return np.nan, np.nan, np.nan
    poc_i = int(np.argmax(hist))      # first max (lowest price) on ties
    # prefer the max closest to the middle on ties
    mx = hist[poc_i]
    cands = np.flatnonzero(hist == mx)
    if len(cands) > 1:
        poc_i = int(cands[np.argmin(np.abs(cands - (len(hist) - 1) / 2))])
    lo = hi = poc_i
    acc = hist[poc_i]
    target = va_pct * total
    n = len(hist)
    while acc < target and (lo > 0 or hi < n - 1):
        up = hist[hi + 1] if hi < n - 1 else -1.0
        dn = hist[lo - 1] if lo > 0 else -1.0
        if up >= dn:
            hi += 1
            acc += hist[hi]
        else:
            lo -= 1
            acc += hist[lo]
    return (base + poc_i) * tick, (base + hi) * tick, (base + lo) * tick


def session_profiles(bars: pd.DataFrame, tick: float, va_pct: float = 0.7, rth_only: bool = True) -> pd.DataFrame:
    """One row per session_date: poc, vah, val, (session high/low/close, volume). Uses ALL bars of that session."""
    b = bars[bars["session_type"] == "RTH"] if (rth_only and "session_type" in bars) else bars
    rows = {}
    for d, g in b.groupby("session_date", sort=True):
        poc, vah, val = profile_levels(g["low"].to_numpy(), g["high"].to_numpy(), g["volume"].to_numpy(), tick, va_pct)
        rows[d] = (poc, vah, val, g["high"].max(), g["low"].min(), g["close"].iloc[-1], g["volume"].sum())
    return pd.DataFrame.from_dict(rows, orient="index", columns=["poc", "vah", "val", "high", "low", "close", "volume"])


def prior_session_levels(bars: pd.DataFrame, tick: float, va_pct: float = 0.7, rth_only: bool = True) -> pd.DataFrame:
    """Per bar: previous session's poc/vah/val/high/low/close, joined on session_date-1 (previous AVAILABLE session).

    Causal by construction: values of session d come from session d-1 which is fully closed
    before any bar of session d (for Globex: the prior RTH profile is complete before the next session's bars).
    """
    prof = session_profiles(bars, tick, va_pct, rth_only)
    cols = ["prior_" + c for c in prof.columns]
    sd = pd.DatetimeIndex(bars["session_date"])
    if len(prof) == 0:
        return pd.DataFrame(np.nan, index=bars.index, columns=cols)
    prof.index = pd.DatetimeIndex(prof.index)
    uniq = pd.DatetimeIndex(sd.unique())
    # for each session date d: the LAST profiled session strictly before d. (A plain shift(1) of the profile table is
    # wrong when d itself has no RTH profile yet, e.g. during the overnight part of a Globex session: it would
    # return the profile of d-1's predecessor / NaN and make the feature depend on where the data is cut.)
    pos = prof.index.searchsorted(uniq, side="left") - 1
    vals = np.full((len(uniq), len(cols)), np.nan)
    ok = pos >= 0
    vals[ok] = prof.to_numpy(float)[pos[ok]]
    per_sess = pd.DataFrame(vals, index=uniq, columns=cols)
    out = per_sess.reindex(sd)
    out.index = bars.index
    return out


def developing_value_area(bars: pd.DataFrame, tick: float, va_pct: float = 0.7, rth_only: bool = True) -> pd.DataFrame:
    """Developing POC/VAH/VAL per bar using only bars of the same session up to and including the current bar."""
    n = len(bars)
    poc = np.full(n, np.nan)
    vah = np.full(n, np.nan)
    val = np.full(n, np.nan)
    lo = bars["low"].to_numpy(float)
    hi = bars["high"].to_numpy(float)
    vol = bars["volume"].to_numpy(float)
    sd = bars["session_date"].to_numpy()
    rth = (bars["session_type"] == "RTH").to_numpy() if (rth_only and "session_type" in bars) else np.ones(n, bool)
    start = 0
    for i in range(n):
        if i == 0 or sd[i] != sd[i - 1]:
            hist, base = None, 0
        if not rth[i]:
            continue
        a, b = int(round(lo[i] / tick)), int(round(hi[i] / tick))
        if hist is None:
            base = a - 200
            hist = np.zeros(1000)
        # grow histogram if needed
        if a < base or b - base >= len(hist):
            new_base = min(base, a - 200)
            new_len = max(len(hist) + (base - new_base), b - new_base + 201)
            nh = np.zeros(new_len)
            nh[base - new_base: base - new_base + len(hist)] = hist
            hist, base = nh, new_base
        hist[a - base: b - base + 1] += vol[i] / (b - a + 1)
        nz = np.flatnonzero(hist)
        sl = hist[nz[0]: nz[-1] + 1]
        poc[i], vah[i], val[i] = _va_from_hist(sl, base + nz[0], tick, va_pct)
    return pd.DataFrame({"dev_poc": poc, "dev_vah": vah, "dev_val": val}, index=bars.index)
