"""Policies: market data -> the target for every close, in payments (+k = hold k payments in cash, -k = be k
payments in debt, 0 = plain DCA).

A policy is a function ``(features) -> pandas Series``. Signals built from market data are shifted one day here
(:func:`lagged`), so the trade at a close never uses that close. Calendar signals (trading days left in the
month) are known in advance and are not shifted.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

Policy = Callable[["object"], "object"]


def lagged(f):
    """Yesterday's signals: what a trade at today's close may use."""
    out = f.shift(1)
    for c in ("tdom", "tdleft"):                       # the calendar is known ahead
        if c in f:
            out[c] = f[c]
    return out


def const(k: float) -> Policy:
    return lambda f: f["tdom"] * 0.0 + k


def turn_of_month(days_before: int = 4, base: float = 0.0, extra: float = 1.0) -> Policy:
    """Invest the next payment ``days_before`` trading days before the month ends instead of on the first day of
    the next: ``extra`` payment more debt from that close until the payment arrives."""
    return lambda f: (base - extra * (f["tdleft"] <= days_before)).clip(-6, 6)


def when(cond: Callable, on: float, off: float = 0.0) -> Policy:
    """``on`` where the condition holds (on yesterday's signals), else ``off``. A missing signal counts as off."""
    def pol(f):
        g = lagged(f)
        c = cond(g).fillna(False).astype(bool)
        return c.map({True: on, False: off}).astype(float)
    return pol


def trend_state(px, ma: int = 200, band: float = 0.0):
    """True while the price is above its ``ma``-day average. With a ``band``, it turns on only above
    average x (1 + band) and off only below average x (1 - band) (fewer flips). NaN until the average exists."""
    avg = px.rolling(ma).mean()
    if band <= 0:
        return (px > avg).where(avg.notna())
    up, down = (px > avg * (1 + band)).to_numpy(), (px < avg * (1 - band)).to_numpy()
    ok = avg.notna().to_numpy()
    out = np.full(len(px), np.nan)
    state = False
    for i in range(len(px)):
        if not ok[i]:
            continue
        if up[i]:
            state = True
        elif down[i]:
            state = False
        out[i] = state
    return px * 0 + out


def trend_policy(ma: int = 200, on: float = -6.0, off: float = 0.0, band: float = 0.0, monthly: bool = False,
                 tom: float = 0.0, veto: Callable | None = None, veto_to: float = 0.0) -> Policy:
    """Be ``on`` payments (borrowed, when negative) while the S&P 500 is above its ``ma``-day average, ``off``
    otherwise. ``monthly``: look only on payment day and keep the answer for the month. ``tom``: that many
    payments more debt over the turn of the month (from 4 trading days before its end). ``veto(signals)``: where
    true (on yesterday's data), use ``veto_to`` instead of ``on``."""
    def pol(f):
        g = lagged(f)
        state = trend_state(g["px"], ma, band)
        t = state.astype(float).map({1.0: on, 0.0: off}).fillna(0.0)
        if veto is not None:
            v = veto(g).fillna(False).astype(bool)
            t = t.where(~(v & (t == on)), veto_to)
        if monthly:
            t = t.where(f["tdom"] == 1).ffill().fillna(0.0)
        if tom:
            t = t - tom * (f["tdleft"] <= 4)
        return t.clip(-6, 6)
    return pol


def votes(f) -> "object":
    """Net count of the signals that pointed the same way in every era of the forecasting study, on yesterday's
    data: +1 each for a volatility spike or a high VIX (fear), falling 10-year yields, a rising high-yield market,
    a bad week (short reversal), heavy policy news; -1 for sharply rising yields, -1 for a falling high-yield
    market."""
    g = lagged(f)
    fear = ((g["rv_ratio"] > 1.3) | (g["vix_pct"] > 0.8)).fillna(False)
    falling = (g["y10_chg"] < 0).fillna(False)
    shock = (g["y10_chg"] > 0.6).fillna(False)
    credit_up = (g["hy_ret63"] > 0.02).fillna(False)
    credit_down = (g["hy_ret63"] < -0.01).fillna(False)
    dip = (g["ret5"] < -0.015).fillna(False)
    news = (g["epu"] > 1.3).fillna(False)
    return (fear.astype(int) + falling.astype(int) + credit_up.astype(int) + dip.astype(int) + news.astype(int)
            - shock.astype(int) - credit_down.astype(int))


def vote_policy(scale: float = 2.0, base: float = 0.0, floor: float = -6.0, cap: float = 6.0, tom: bool = False) -> Policy:
    """Debt grows with the votes: target = base - scale x votes, between ``floor`` and ``cap``; with ``tom`` one
    more payment of debt over the turn of the month."""
    def pol(f):
        t = base - scale * votes(f)
        if tom:
            t = t - (f["tdleft"] <= 4)
        return t.clip(floor, cap).astype(float)
    return pol


def smooth(policy: Policy, min_step: float = 1.0) -> Policy:
    """Round a policy's target to whole payments (``min_step``)."""
    return lambda f: (policy(f) / min_step).round() * min_step


def to_array(policy: Policy, f) -> np.ndarray:
    t = policy(f)
    return np.nan_to_num(np.asarray(t, dtype=float), nan=0.0)
