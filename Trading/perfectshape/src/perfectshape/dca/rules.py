"""Exposure rules: market signals -> position / equity wanted at each close (1.0 = plain DCA, 1.1 = borrowed 10%
of the account, 0.8 = a fifth in cash). Every rule reads yesterday's signals (:func:`perfectshape.dca.policy.lagged`).

A :class:`Rule` also says how it comes down: ``sell=True`` sells shares to repay or to raise cash; ``sell=False``
never sells and lets the monthly payments repay the debt.

Building blocks:

* :func:`ladder`  borrow more the deeper the market has fallen from its high, until it recovers ("crash 10%:
  borrow 10% of the account");
* :func:`trend`   one exposure above the 200-day average, another below;
* :func:`switch`  an exposure while a signal (VIX, volatility, policy news ...) is beyond a level, with separate
  on / off levels;
* :func:`vol_target`  exposure inversely to recent volatility;
* :func:`both`, :func:`highest`, :func:`unless`, :func:`floor_below_trend`  combine them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from perfectshape.dca.policy import lagged, trend_state

Exposure = Callable[["object"], "object"]


@dataclass(frozen=True)
class Rule:
    name: str
    exposure: Exposure
    sell: bool = False
    family: str = ""

    def array(self, f) -> np.ndarray:
        return np.nan_to_num(np.asarray(self.exposure(f), dtype=float), nan=1.0)


def flat(e: float = 1.0) -> Exposure:
    return lambda f: f["px"] * 0.0 + e


def ladder(tiers: list[tuple[float, float]], exit: float = -0.02, col: str = "dd_ath", confirm: int = 0) -> Exposure:
    """Borrow by steps as the market falls: ``tiers`` = [(drawdown, extra exposure), ...], e.g. [(-0.10, 0.10)] =
    borrow 10% of the account once the index is 10% under its high. The deepest step reached stays on until the
    drawdown is back above ``exit``. ``confirm`` > 0: a step is taken only on a day the index is above its
    ``confirm``-day average (the fall has paused)."""
    tiers = sorted(tiers, key=lambda x: -x[0])

    def fn(f):
        g = lagged(f)
        dd = g[col].to_numpy()
        ok = np.ones(len(dd), dtype=bool)
        if confirm:
            ok = (g["px"] > g["px"].rolling(confirm).mean()).fillna(False).to_numpy()
        out = np.ones(len(dd))
        level = 0.0
        for i in range(len(dd)):
            d = dd[i]
            if not np.isfinite(d):
                continue
            if d >= exit:
                level = 0.0
            elif ok[i]:
                for depth, extra in tiers:
                    if d <= depth and extra > level:
                        level = extra
            out[i] = 1.0 + level
        return f["px"] * 0.0 + out
    return fn


def trend(up: float = 1.25, down: float = 1.0, ma: int = 200, band: float = 0.0, monthly: bool = False) -> Exposure:
    """``up`` while the index is above its ``ma``-day average, ``down`` below."""
    def fn(f):
        g = lagged(f)
        st = trend_state(g["px"], ma, band).astype(float)
        e = st.map({1.0: up, 0.0: down}).fillna(1.0)
        if monthly:
            e = e.where(f["tdom"] == 1).ffill().fillna(1.0)
        return e
    return fn


def switch(col: str, on: float, off: float, level: float, rest: float = 1.0) -> Exposure:
    """``level`` from the day ``col`` passes ``on`` until it comes back past ``off`` (on > off: a high reading
    switches it on; on < off: a low one), ``rest`` otherwise. Missing data = rest."""
    high = on > off

    def fn(f):
        v = lagged(f)[col].to_numpy()
        out = np.full(len(v), rest)
        state = False
        for i in range(len(v)):
            x = v[i]
            if np.isfinite(x):
                if (x >= on) if high else (x <= on):
                    state = True
                elif (x <= off) if high else (x >= off):
                    state = False
            else:
                state = False
            if state:
                out[i] = level
        return f["px"] * 0.0 + out
    return fn


def vol_target(target: float = 15.0, lo: float = 1.0, hi: float = 1.5, col: str = "rv21", monthly: bool = True) -> Exposure:
    """Exposure = target volatility / recent volatility, between ``lo`` and ``hi``."""
    def fn(f):
        e = (target / lagged(f)[col]).clip(lo, hi).fillna(1.0)
        if monthly:
            e = e.where(f["tdom"] == 1).ffill().fillna(1.0)
        return e
    return fn


def highest(*rules: Exposure) -> Exposure:
    return lambda f: np.maximum.reduce([np.asarray(r(f), dtype=float) for r in rules]) + f["px"] * 0.0


def both(a: Exposure, b: Exposure) -> Exposure:
    """Add the borrowing of two rules (and the cash of two rules)."""
    return lambda f: a(f) + b(f) - 1.0


def unless(rule: Exposure, cond: Callable, to: float = 1.0) -> Exposure:
    """``rule``, but no more than ``to`` while ``cond(yesterday's signals)`` holds (a guard)."""
    def fn(f):
        e = rule(f)
        c = cond(lagged(f)).fillna(False).astype(bool)
        return e.where(~c, np.minimum(e, to))
    return fn


def only_if(rule: Exposure, cond: Callable) -> Exposure:
    """``rule``'s borrowing only while ``cond(yesterday's signals)`` holds; 1.0 otherwise."""
    def fn(f):
        e = rule(f)
        c = cond(lagged(f)).fillna(False).astype(bool)
        return e.where(c | (e <= 1.0), 1.0)
    return fn


def rate_guard(rise: float = 0.6, days: int = 126) -> Callable:
    return lambda g: (g["y10"] - g["y10"].shift(days)) > rise
