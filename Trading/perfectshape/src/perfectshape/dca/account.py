"""The saver's account, simulated for many start dates at once.

Every month a payment arrives on the first trading day. Each day, after the close, the account compares its cash
with the policy's **target**: a number of payments, +k = hold k payments in cash (skipped), -k = be k payments
in debt (borrowed and invested early), 0 = plain DCA. Cash above the target is invested at that close; the account
never sells (except on a margin call), so it reaches a higher target only by letting payments pile up.

Rules of the study (:class:`AccountConfig`):

* at most ``max_months`` payments in cash and at most ``max_months`` payments of debt;
* debt costs the 10-year Treasury yield, cash earns the 3-month T-bill yield, both accrued daily;
* a new loan must leave equity of at least ``initial_margin`` (50%, Reg T) of the position, so a young account
  cannot borrow much; if equity falls under ``maintenance`` (30%) of the position, shares are sold to restore it.

The target for a close must be built from data up to the *previous* close (policies shift their signals).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AccountConfig:
    payment: float = 2000.0
    max_months: float = 6.0
    initial_margin: float = 0.50
    maintenance: float = 0.30
    cash_earns: bool = True          # idle cash earns the T-bill yield (False: nothing)
    borrow_spread: float = 0.0       # added to the 10-year yield, a year (0.01 = one point more)
    trade_cost: float = 0.0          # share of every purchase lost to costs


def pay_days(dates: np.ndarray) -> np.ndarray:
    """True on the first trading day of each month."""
    m = dates.astype("datetime64[M]")
    out = np.ones(len(dates), dtype=bool)
    out[1:] = m[1:] != m[:-1]
    return out


def simulate(tr: np.ndarray, dates: np.ndarray, target: np.ndarray, y10: np.ndarray, y3m: np.ndarray,
             cfg: AccountConfig = AccountConfig(), starts: np.ndarray | None = None, ends: np.ndarray | None = None,
             path: bool = False) -> dict:
    """Run accounts that open at bar ``starts[i]`` (a payment day) and are valued at bar ``ends[i]``.

    ``tr`` total-return index, ``target`` payments of cash (+) / debt (-) wanted at each close, ``y10`` / ``y3m``
    yields in percent a year. Returns per account: ``wealth`` (shares + cash at the end), ``paid`` (payments
    received), ``shares``, ``cash``, ``interest`` (net interest paid, positive = cost), ``margin_calls``,
    ``min_cash`` / ``max_cash``, ``debt_days``, ``cash_days``; with ``path`` (single account) also the daily
    ``wealth_path``, ``cash_path`` and ``invested_path``.
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
    cap = cfg.max_months * cfg.payment
    shares = np.zeros(n)
    cash = np.zeros(n)
    paid = np.zeros(n)
    interest = np.zeros(n)
    calls = np.zeros(n, dtype=int)
    lo = np.zeros(n)
    hi = np.zeros(n)
    debt_days = np.zeros(n, dtype=int)
    cash_days = np.zeros(n, dtype=int)
    out_w = np.zeros(n)
    out_s = np.zeros(n)
    out_c = np.zeros(n)
    if path:
        wp, cp, ip = np.zeros(T), np.zeros(T), np.zeros(T)
    for t in range(int(starts.min()), int(ends.max()) + 1):
        live = (starts <= t) & (t <= ends)
        if not live.any():
            continue
        p = tr[t]
        # interest since the previous close
        i = np.where(cash < 0, cash * r_debt[t], cash * r_cash[t]) * (starts < t)
        cash += i * live
        interest -= i * live
        if pay[t]:
            cash += cfg.payment * live
            paid += cfg.payment * live
        pos = shares * p
        # margin call: sell enough to bring equity back to the maintenance share of the position
        equity = pos + cash
        call = live & (cash < 0) & (equity < cfg.maintenance * pos)
        if call.any():
            sell = np.where(call, np.minimum(pos, pos - np.maximum(equity, 0.0) / cfg.maintenance), 0.0)
            shares -= sell / p
            cash += sell
            calls += call
            pos = shares * p
        want = np.clip(target[t], -cfg.max_months, cfg.max_months) * cfg.payment
        buy = np.maximum(cash - want, 0.0)
        # borrowing: no more than the cap, and Reg T on the new position: equity >= initial_margin * position
        room = np.maximum(cash, 0.0) + np.maximum(
            np.minimum(cap + np.minimum(cash, 0.0),
                       (pos * (1.0 - cfg.initial_margin) + np.minimum(cash, 0.0)) / cfg.initial_margin
                       + np.maximum(cash, 0.0) * (1.0 - cfg.initial_margin) / cfg.initial_margin), 0.0)
        buy = np.minimum(buy, room) * live
        buy = np.maximum(buy, (cash - cap) * live)                 # never more than the cap in cash
        buy = np.maximum(buy, 0.0)
        shares += buy * (1.0 - cfg.trade_cost) / p
        cash -= buy
        lo = np.minimum(lo, cash)
        hi = np.maximum(hi, cash)
        debt_days += live & (cash < -1e-9)
        cash_days += live & (cash > 1e-9)
        done = ends == t
        if done.any():
            out_w[done] = (shares * p + cash)[done]
            out_s[done] = shares[done]
            out_c[done] = cash[done]
        if path:
            wp[t], cp[t], ip[t] = shares[0] * p + cash[0], cash[0], paid[0]
    res = {"wealth": out_w, "paid": paid, "shares": out_s, "cash": out_c, "interest": interest, "margin_calls": calls,
           "min_cash": lo, "max_cash": hi, "debt_days": debt_days, "cash_days": cash_days}
    if path:
        res |= {"wealth_path": wp, "cash_path": cp, "invested_path": ip}
    return res


def best_possible(tr: np.ndarray, dates: np.ndarray, y10: np.ndarray, y3m: np.ndarray, cfg: AccountConfig = AccountConfig(),
                  start: int = 0, end: int | None = None, step: float = 1.0) -> np.ndarray:
    """The target path of a saver who knows every future price: the ceiling on what timing can add.

    Dynamic programme over (day, cash in units of ``step`` payments), valuing a purchase by what it is worth at
    the end and interest at face value. Margin limits are ignored (they bind only in an account's first year),
    so the path is fed back through :func:`simulate` to get its true result."""
    end = len(tr) - 1 if end is None else end
    pay = pay_days(dates)
    days = np.zeros(len(tr))
    days[1:] = (dates[1:] - dates[:-1]).astype("timedelta64[D]").astype(float)
    r_debt = (y10 / 100.0 + cfg.borrow_spread) * days / 365.0
    r_cash = (y3m / 100.0 * days / 365.0) if cfg.cash_earns else np.zeros(len(tr))
    K = int(round(cfg.max_months / step))
    ks = np.arange(-K, K + 1) * step                      # cash after trading, in payments
    nk = len(ks)
    add = int(round(1.0 / step))
    ids = np.arange(nk)
    gain = tr[end] / tr[start:end + 1]                     # what one payment bought on day t is worth at the end
    choice = np.zeros((end - start + 1, nk), dtype=np.int16)
    cont = ks.copy()                                       # value of ending day t with cash ks[b]; last day: face value
    for t in range(end, start - 1, -1):
        g = gain[t - start]
        # W(a): arrive with cash ks[a] (payment included), end the day at any b <= a having bought the difference
        m = cont - ks * g
        run = np.maximum.accumulate(m)
        choice[t - start] = np.maximum.accumulate(np.where(m >= run, ids, 0))
        W = ks * g + run
        if t > start:
            # the day before: interest over the night on the balance carried, then today's payment arrives; a
            # payment that would overflow the cash cap is invested today
            idx = ids + (add if pay[t] else 0)
            over = np.maximum(idx - (nk - 1), 0)
            cont = ks * np.where(ks < 0, r_debt[t], r_cash[t]) + W[np.minimum(idx, nk - 1)] + over * step * g
    target = np.zeros(len(tr))
    a = K                                                  # no cash before the first payment
    for t in range(start, end + 1):
        if pay[t]:
            a = min(a + add, nk - 1)
        a = int(choice[t - start, a])
        target[t] = ks[a]
    return target
