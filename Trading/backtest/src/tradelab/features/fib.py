"""Fibonacci retracement zones from confirmed swing legs."""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_LEVELS = (0.705, 0.786, 0.886)


def impulse_leg(sw: pd.DataFrame, min_size=None, direction: str = "both") -> pd.DataFrame:
    """Most recent COMPLETED impulse leg, evaluated causally at every bar.

    A leg is born at the bar where its closing pivot is CONFIRMED (``swing_high_new`` / ``swing_low_new``, i.e. pivot
    bar + k):
      * up-leg   (+1): a confirmed swing high H closes the leg that started at the most recent confirmed swing low L
        whose pivot lies before H;
      * down-leg (-1): a confirmed swing low L closes the leg that started at the most recent confirmed swing high H
        before it.
    A leg is an *impulse* leg only if ``H - L >= min_size``. ``min_size`` is a scalar (price points) or a bar-indexed
    Series/array evaluated at the confirmation bar (e.g. ``min_leg_atr * atr``); ``None`` = every leg qualifies.
    The output at bar i is the latest qualifying leg confirmed at or before i (forward-filled), so a SMALL pullback
    swing does not replace the impulse leg it is retracing: with ``min_size`` set, an up-leg survives the shallow
    swing low that confirms during its pullback (this is the leg a fib retracement zone is drawn on). With
    ``min_size=None`` the most recent pivot decides the direction (an up-leg flips to the pullback down-leg as soon as the
    pullback low confirms). ``direction="up"`` / ``"down"`` only builds legs of that direction.

    Columns: direction (+1 / -1 / 0 = none yet), leg_low, leg_high (the endpoints), leg_end_pos (positional index of the
    closing pivot). Nothing here looks beyond bar i. NOTE: strategies/vp_fib_orderflow.py keeps its own stateful leg
    tracking (it also expires a leg on a new high and applies leg_scope); this helper does not replicate that.
    """
    if direction not in ("both", "up", "down"):
        raise ValueError("direction must be both|up|down")
    n = len(sw)
    sh_new = sw["swing_high_new"].to_numpy(bool)
    sl_new = sw["swing_low_new"].to_numpy(bool)
    hp, hpx = sw["last_swing_high_pos"].to_numpy(float), sw["last_swing_high"].to_numpy(float)
    lp, lpx = sw["last_swing_low_pos"].to_numpy(float), sw["last_swing_low"].to_numpy(float)
    if min_size is None:
        ms = np.zeros(n)
    elif np.isscalar(min_size):
        ms = np.full(n, float(min_size))
    else:
        ms = np.asarray(pd.Series(min_size).reindex(sw.index) if isinstance(min_size, pd.Series) else min_size, float)
    d_out = np.zeros(n, dtype=int)
    lo_out = np.full(n, np.nan)
    hi_out = np.full(n, np.nan)
    end_out = np.full(n, np.nan)
    lows: list[tuple[float, float]] = []
    highs: list[tuple[float, float]] = []
    cur = (0, np.nan, np.nan, np.nan)
    for i in range(n):
        events = []
        if sl_new[i]:
            events.append((lp[i], "L"))
        if sh_new[i]:
            events.append((hp[i], "H"))
        for pos, kind in sorted(events):       # earlier pivot first: the later one decides when both confirm together
            if kind == "L":
                lows.append((lp[i], lpx[i]))
                if direction != "up":
                    start = next((px for p_, px in reversed(highs) if p_ < pos), None)
                    if start is not None and start > lpx[i] and (start - lpx[i]) >= ms[i] * (1 - 1e-12) and (ms[i] == ms[i]):
                        cur = (-1, lpx[i], start, pos)
            else:
                highs.append((hp[i], hpx[i]))
                if direction != "down":
                    start = next((px for p_, px in reversed(lows) if p_ < pos), None)
                    if start is not None and hpx[i] > start and (hpx[i] - start) >= ms[i] * (1 - 1e-12) and (ms[i] == ms[i]):
                        cur = (1, start, hpx[i], pos)
        d_out[i], lo_out[i], hi_out[i], end_out[i] = cur
    return pd.DataFrame({"direction": d_out, "leg_low": lo_out, "leg_high": hi_out, "leg_end_pos": end_out}, index=sw.index)


def retracement_price(leg_low, leg_high, direction, level):
    """Price at retracement `level` of the leg (level measured back from the leg extreme).

    up-leg: high - level*(high-low); down-leg: low + level*(high-low).
    """
    rng = np.asarray(leg_high, float) - np.asarray(leg_low, float)
    d = np.asarray(direction)
    return np.where(d >= 0, np.asarray(leg_high, float) - level * rng, np.asarray(leg_low, float) + level * rng)


def fib_zone(leg: pd.DataFrame, lo_level: float = 0.705, hi_level: float = 0.886) -> pd.DataFrame:
    """Zone between two retracement levels: zone_lo <= zone_hi in price. NaN where no leg."""
    a = retracement_price(leg["leg_low"], leg["leg_high"], leg["direction"], lo_level)
    b = retracement_price(leg["leg_low"], leg["leg_high"], leg["direction"], hi_level)
    z = pd.DataFrame({"zone_lo": np.minimum(a, b), "zone_hi": np.maximum(a, b), "invalid_level": retracement_price(leg["leg_low"], leg["leg_high"], leg["direction"], hi_level)}, index=leg.index)
    z[leg["direction"].to_numpy() == 0] = np.nan
    return z


def zone_outside_value(zone_lo, zone_hi, val, vah) -> pd.Series:
    """True when the zone lies entirely below VAL (discount) or entirely above VAH (premium)."""
    zl, zh, v, h = (pd.Series(x) if not isinstance(x, pd.Series) else x for x in (zone_lo, zone_hi, val, vah))
    return ((zh < v) | (zl > h)) & zl.notna() & v.notna()


def price_location(price, val, vah) -> pd.Series:
    """-1 discount (below VAL), 0 inside value, +1 premium (above VAH), NaN if levels unknown."""
    price = pd.Series(price) if not isinstance(price, pd.Series) else price
    out = pd.Series(0.0, index=price.index)
    out[price < val] = -1.0
    out[price > vah] = 1.0
    out[val.isna() | vah.isna()] = np.nan
    return out
