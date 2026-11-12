"""The saver's account when borrowing is sized against the account itself, not counted in payments.

A rule sets the **exposure** wanted at each close: position / equity. 1.0 is plain DCA (everything invested, no
debt), 1.10 is "borrowed 10% of the account", 0.8 is a fifth of the account in cash. Two ways down from a higher
exposure: ``sell=True`` sells shares to repay (and sells into cash below 1.0), ``sell=False`` never sells: the
monthly payments repay the debt, as in :mod:`perfectshape.dca.account`.

Rules of the account: debt costs the 10-year Treasury yield (+ ``borrow_spread``), cash earns the 3-month bill
yield, a purchase on margin must leave equity of at least ``initial_margin`` of the position (Reg T, 50%: at most
2.0 exposure), and when equity falls under ``maintenance`` (30%) of the position shares are sold to restore it.
The account trades only when it is off its target by more than ``band`` of equity (payments are always
invested), every trade costs ``trade_cost``.

Besides final wealth the simulator tracks each account's **drawdown** on its time-weighted value (payments
taken out, so a deposit is not a gain), which is what makes a levered saver comparable with plain DCA.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perfectshape.dca.account import pay_days


@dataclass(frozen=True)
class ExposureConfig:
    payment: float = 2000.0
    initial_margin: float = 0.50
    maintenance: float = 0.30
    band: float = 0.02               # trade when off target by more than this share of equity
    trade_cost: float = 0.0005       # 5 bps of every trade (payments included)
    borrow_spread: float = 0.0
    cash_earns: bool = True
    max_debt: float = float("inf")   # debt at most this many payments (inf = only the margin rules limit it)
    max_cash: float = float("inf")   # cash at most this many payments: beyond it, payments are invested


def simulate_exposure(tr: np.ndarray, dates: np.ndarray, exposure: np.ndarray, y10: np.ndarray, y3m: np.ndarray,
                      cfg: ExposureConfig = ExposureConfig(), sell: bool = False, starts: np.ndarray | None = None,
                      ends: np.ndarray | None = None, path: bool = False) -> dict:
    """Accounts opened at ``starts`` and valued at ``ends`` (bars), all following ``exposure`` (T,).

    Per account: ``wealth``, ``paid``, ``max_dd`` (deepest fall of the time-weighted value, negative),
    ``interest`` (net paid), ``margin_calls``, ``wiped`` (equity went to zero), ``avg_exposure``,
    ``max_exposure``, ``traded`` (dollars traded beyond the payments); with ``path`` (one account) also
    ``wealth_path``, ``unit_path`` (time-weighted value), ``exposure_path``.
    """
    T = len(tr)
    starts = np.array([0]) if starts is None else np.asarray(starts)
    ends = np.full(len(starts), T - 1) if ends is None else np.asarray(ends)
    n = len(starts)
    pay = pay_days(dates)
    days = np.zeros(T)
    days[1:] = (dates[1:] - dates[:-1]).astype("timedelta64[D]").astype(float)
    r_debt = (y10 / 100.0 + cfg.borrow_spread) * days / 365.0
    r_cash = (y3m / 100.0 * days / 365.0) if cfg.cash_earns else np.zeros(T)
    max_e = 1.0 / cfg.initial_margin
    shares, cash, paid, interest = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    calls = np.zeros(n, dtype=int)
    wiped = np.zeros(n, dtype=bool)
    unit, peak, mdd = np.ones(n), np.ones(n), np.zeros(n)
    prev_w = np.zeros(n)
    exp_sum, exp_max, exp_n, traded = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    out_w = np.zeros(n)
    if path:
        wp, up, ep = np.zeros(T), np.ones(T), np.zeros(T)
    for t in range(int(starts.min()), int(ends.max()) + 1):
        live = (starts <= t) & (t <= ends)
        if not live.any():
            continue
        p = tr[t]
        i = np.where(cash < 0, cash * r_debt[t], cash * r_cash[t]) * (starts < t)
        cash += i * live
        interest -= i * live
        flow = cfg.payment * live if pay[t] else 0.0
        cash += flow
        paid += flow
        pos = shares * p
        equity = pos + cash
        # time-weighted value: today's wealth before the payment over yesterday's wealth
        grew = live & (prev_w > 0)
        unit = np.where(grew, unit * np.maximum(equity - flow, 0.0) / np.where(prev_w > 0, prev_w, 1.0), unit)
        peak = np.maximum(peak, unit)
        mdd = np.minimum(mdd, unit / peak - 1.0)
        wiped |= live & (prev_w > 0) & (equity - flow <= 0)
        # margin call
        call = live & (cash < 0) & (equity < cfg.maintenance * pos)
        if call.any():
            s = np.where(call, np.minimum(pos, pos - np.maximum(equity, 0.0) / cfg.maintenance), 0.0)
            shares -= s / p
            cash += s * (1.0 - cfg.trade_cost)
            calls += call
            traded += s
            pos = shares * p
            equity = pos + cash
        want = np.clip(exposure[t], 0.0, max_e) * np.maximum(equity, 0.0)
        diff = want - pos
        off = np.abs(diff) > cfg.band * np.maximum(equity, 0.0)
        buy = np.where(off & (diff > 0), diff, np.clip(np.minimum(cash, diff), 0.0, None))     # always invest a payment
        buy = np.clip(np.minimum(buy, max_e * np.maximum(equity, 0.0) - pos), 0.0, None) * live
        if np.isfinite(cfg.max_debt):
            buy = np.minimum(buy, np.maximum(cash + cfg.max_debt * cfg.payment, 0.0))
        if np.isfinite(cfg.max_cash):
            buy = np.maximum(buy, (cash - cfg.max_cash * cfg.payment) * live)
        sold = np.where(off & (diff < 0), -diff, 0.0) * live if sell else 0.0
        shares += (buy * (1.0 - cfg.trade_cost) - sold) / p
        cash += sold * (1.0 - cfg.trade_cost) - buy
        traded += (buy - np.minimum(buy, flow) + sold)
        pos = shares * p
        w = pos + cash
        prev_w = np.where(live, w, prev_w)
        e_now = np.where(w > 0, pos / np.where(w > 0, w, 1.0), 0.0)
        exp_sum += e_now * live
        exp_n += live
        exp_max = np.maximum(exp_max, e_now * live)
        done = ends == t
        if done.any():
            out_w[done] = w[done]
        if path:
            wp[t], up[t], ep[t] = w[0], unit[0], e_now[0]
    res = {"wealth": out_w, "paid": paid, "max_dd": mdd, "interest": interest, "margin_calls": calls, "wiped": wiped,
           "avg_exposure": exp_sum / np.maximum(exp_n, 1), "max_exposure": exp_max, "traded": traded}
    if path:
        res |= {"wealth_path": wp, "unit_path": up, "exposure_path": ep}
    return res
