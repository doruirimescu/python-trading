"""The mega strategy: any asset, long or short, with leverage, against plain DCA into the S&P 500.

Assets (daily total returns, :func:`assets`): the S&P 500 (1928 on), the Nasdaq-100 (1985 on, price only), a
10-year Treasury held at constant maturity (built from the 10-year yield), gold (2000 on) and T-bills. Leverage is
taken the way a saver can take it without margin calls: daily-reset leveraged funds, modelled as
``L x index return - (L - 1) x (bill rate + spread) - fee`` (:func:`leveraged`; checked against UPRO, TQQQ, TMF).

A strategy (:class:`Mega`) is a set of weights per day decided on closes up to two days before the return it earns
(the signal of day t-1 is traded at the close of day t). Because every dollar of the account follows the same
weights, the account's time-weighted value is the strategy's return series: CAGR, Sharpe and drawdown are read off
it, and a saver's final wealth is his payments compounded along it (:func:`dca_stats`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from perfectshape.dca.account import pay_days

ERAS = {"1928-1961": ("1928-01-01", "1961-12-31"), "1962-1985": ("1962-01-01", "1985-12-31"),
        "1986-1999": ("1986-01-01", "1999-12-31"), "2000-2012": ("2000-01-01", "2012-12-31"),
        "2013-today": ("2013-01-01", "2100-01-01")}


def bond_returns(y10, days):
    """Daily total return of a 10-year par Treasury rolled daily: carry at yesterday's yield plus the price change
    from the yield move (modified duration and convexity of a 10-year par bond at yesterday's yield)."""
    y = (y10 / 100.0).ffill()
    y0 = y.shift(1)
    d = (1.0 - (1.0 + y0 / 2.0) ** -20) / y0.clip(lower=1e-4)
    conv = d * d + d                                   # close enough for a par bond
    dy = y - y0
    return (y0 * days / 365.0 - d * dy + 0.5 * conv * dy * dy).fillna(0.0)


def assets(cache_dir: str | Path | None = None, refresh: bool = False):
    """DataFrame of daily simple returns ``spx, ndx, bond, gold, bill`` (NaN before an asset exists) plus ``px`` (the
    S&P 500 price), ``y10`` and ``days`` (calendar days since the previous bar), 1928 to today."""
    import pandas as pd

    from perfectshape.dca.data import PROJECT_ROOT, _yahoo
    from perfectshape.dca.pages import _markets

    cache_dir = Path(cache_dir or os.environ.get("PERFECTSHAPE_DCA_CACHE", PROJECT_ROOT / "data_cache" / "dca"))
    path = cache_dir / "mega_assets.pkl"
    if path.exists() and not refresh:
        return pd.read_pickle(path)
    m = _markets()["all"]
    a = pd.DataFrame(index=m.index)
    a["px"], a["y10"] = m["px"], m["y10"]
    a["days"] = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1).to_numpy()
    a["spx"] = m["tr"].pct_change().fillna(0.0)
    a["bill"] = (m["y3m"].fillna(0.0) / 100.0 * a["days"] / 365.0)
    a["bond"] = bond_returns(m["y10"], a["days"])
    for col, ticker in (("ndx", "^NDX"), ("gold", "GC=F")):
        s = _yahoo_from(ticker, _yahoo)
        a[col] = s.reindex(a.index).ffill().pct_change()
        a.loc[a.index <= s.index[0], col] = np.nan
    cache_dir.mkdir(parents=True, exist_ok=True)
    a.to_pickle(path)
    return a


def _yahoo_from(ticker, _yahoo, start="1970-01-01"):
    import yfinance as yf

    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    s = df["Close"]
    s = s.iloc[:, 0] if getattr(s, "ndim", 1) > 1 else s
    return s.dropna().astype(float)


def leveraged(r, bill, lev: float, spread: float = 0.005, fee: float = 0.0095, days=None):
    """Daily return of a daily-reset ``lev`` x fund on index return ``r``: financing of the borrowed part at the bill
    rate + ``spread`` and a yearly ``fee`` (1x: the index itself, no cost)."""
    if lev == 1:
        return r
    d = 1.0 if days is None else days
    return lev * r - (lev - 1.0) * (bill + spread * d / 365.0) - fee * d / 365.0


@dataclass(frozen=True)
class Mega:
    """Leveraged trend rotation.

    Risk-on (the S&P 500 above its ``ma``-day average by ``band``; stays on until it is below by ``band``): hold the
    ``lev`` x equity fund, ``ndx`` of it in the Nasdaq-100 (when it exists), scaled down so that its volatility
    (last ``vol_days`` days, times ``lev``) does not exceed ``vol_target`` (None: always full).
    Everything not in equities sits in the safe asset: the 10-year Treasury (``bond_lev`` x) while it is above its own
    ``ma``-day average, otherwise gold while it is above its average (``gold``), otherwise T-bills.
    ``guard``: no leverage (1x) while the 10-year yield has risen more than ``guard`` points in 6 months."""

    lev: float = 3.0
    ma: int = 200
    band: float = 0.01
    ndx: float = 0.0
    vol_target: float | None = 0.25
    vol_days: int = 21
    bond_lev: float = 1.0
    gold: bool = True
    guard: float | None = None
    off_equity: float = 0.0        # equity weight (1x S&P) kept in risk-off; 0 = all in the safe asset
    rebalance: float = 0.10        # re-size the equity share when it is off its target by more than this
    cost: float = 0.001            # of every dollar traded
    spread: float = 0.005          # the funds' financing over the bill rate
    lag: int = 2                   # days between a signal's close and the first return it earns

    def weights(self, a):
        """DataFrame of held weights ``eq`` (in the leveraged equity fund), ``eq1`` (in the plain S&P 500), ``bond``,
        ``gold``, ``bill`` per day, already lagged."""
        import pandas as pd

        px = a["px"]
        avg = px.rolling(self.ma).mean()
        up, dn = (px > avg * (1 + self.band)).to_numpy(), (px < avg * (1 - self.band)).to_numpy()
        on = np.zeros(len(a), dtype=bool)
        state = False
        for i in range(len(a)):
            if up[i]:
                state = True
            elif dn[i]:
                state = False
            on[i] = state
        rv = np.log(px).diff().rolling(self.vol_days).std() * np.sqrt(252)
        if self.vol_target:
            scale = (self.vol_target / (self.lev * rv)).clip(upper=1.0).fillna(0.0).to_numpy()
        else:
            scale = np.ones(len(a))
        want = np.where(on, scale, 0.0)
        held = np.zeros(len(a))
        h = 0.0
        for i in range(len(a)):                        # re-size only on a switch or a large enough gap
            w = want[i]
            if (w == 0.0) != (h == 0.0) or abs(w - h) > self.rebalance * max(h, 1e-9):
                h = w
            held[i] = h
        bond_i = (1.0 + leveraged(a["bond"], a["bill"], self.bond_lev, self.spread, days=a["days"])).cumprod()
        bond_up = (bond_i > bond_i.rolling(self.ma).mean()).to_numpy()
        gold_i = (1.0 + a["gold"].fillna(0.0)).cumprod()
        gold_up = ((gold_i > gold_i.rolling(self.ma).mean()) & a["gold"].notna()).to_numpy() & self.gold
        w = pd.DataFrame(index=a.index)
        lever = np.ones(len(a), dtype=bool)
        if self.guard is not None:
            lever = ~((a["y10"] - a["y10"].shift(126)) > self.guard).to_numpy()
        eq1_off = np.where(on, 0.0, self.off_equity)
        w["eq"] = np.where(lever, held, 0.0)
        w["eq1"] = np.where(lever, 0.0, np.minimum(held * self.lev, 1.0)) + eq1_off
        rest = 1.0 - w["eq"] - w["eq1"]
        w["bond"] = np.where(bond_up, rest, 0.0)
        w["gold"] = np.where(~bond_up & gold_up, rest, 0.0)
        w["bill"] = rest - w["bond"] - w["gold"]
        return w.shift(self.lag).fillna({"eq": 0.0, "eq1": 0.0, "bond": 0.0, "gold": 0.0, "bill": 1.0})

    def returns(self, a):
        """(daily strategy return, weights)."""
        w = self.weights(a)
        d = a["days"]
        ndx = a["ndx"].where(a["ndx"].notna(), a["spx"])
        eq = ((1.0 - self.ndx) * leveraged(a["spx"], a["bill"], self.lev, self.spread, days=d)
              + self.ndx * leveraged(ndx, a["bill"], self.lev, self.spread, days=d))
        r = (w["eq"] * eq + w["eq1"] * a["spx"] + w["bond"] * leveraged(a["bond"], a["bill"], self.bond_lev, self.spread, days=d)
             + w["gold"] * a["gold"].fillna(0.0) + w["bill"] * a["bill"])
        traded = w.diff().abs().sum(axis=1).fillna(0.0) / 2.0
        return r - traded * self.cost, w


def perf(r, bill, first: str | None = None, last: str | None = None) -> dict:
    """CAGR, volatility, Sharpe (over T-bills), deepest fall of a daily return series within [first, last]."""
    if first or last:
        keep = (r.index >= (first or "1900")) & (r.index <= (last or "2200"))
        r, bill = r[keep], bill[keep]
    if len(r) < 60:
        return {"n": 0}
    u = (1.0 + r).cumprod()
    years = (r.index[-1] - r.index[0]).days / 365.25
    ex = r - bill
    return {"n": len(r), "cagr": float(u.iloc[-1] ** (1 / years) - 1.0), "vol": float(r.std() * np.sqrt(252)),
            "sharpe": float(ex.mean() / r.std() * np.sqrt(252)), "max_dd": float((u / u.cummax() - 1.0).min()),
            "worst_year": float(r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1).min())}


def dca_stats(r, base, dates, years: int = 10, first: str | None = None, last: str | None = None, step: int = 3,
              payment: float = 2000.0) -> dict:
    """Savers paying ``payment`` on every payment day for ``years``, opened every ``step``-th payment day in
    [first, last]: each one's final wealth following return series ``r`` against following ``base`` (plain DCA)."""
    u, b = np.cumprod(1.0 + np.asarray(r)), np.cumprod(1.0 + np.asarray(base))
    pay = np.flatnonzero(pay_days(dates))
    lo = np.datetime64(first) if first else dates[0]
    hi = np.datetime64(last) if last else dates[-1]
    edges, dd, dd_b, starts = [], [], [], []
    for j in range(0, len(pay), step):
        s = pay[j]
        if dates[s] < lo or j + years * 12 >= len(pay):
            continue
        e = pay[j + years * 12]
        if dates[e] > hi:
            break
        p = pay[j:j + years * 12]
        wu, wb = payment * (u[e] / u[p]).sum(), payment * (b[e] / b[p]).sum()
        edges.append(wu / wb - 1.0)
        su, sb = u[s:e + 1], b[s:e + 1]
        dd.append((su / np.maximum.accumulate(su) - 1.0).min())
        dd_b.append((sb / np.maximum.accumulate(sb) - 1.0).min())
        starts.append(dates[s])
    e, dd, dd_b = np.array(edges), np.array(dd), np.array(dd_b)
    if not len(e):
        return {"n": 0}
    return {"n": len(e), "win": float((e > 0).mean()), "median": float(np.median(e)), "p10": float(np.quantile(e, 0.1)),
            "worst": float(e.min()), "best": float(e.max()), "dd_median": float(np.median(dd)), "dd_worst": float(dd.min()),
            "dd_vs_dca": float(np.median(dd - dd_b)), "dd_vs_dca_worst": float((dd - dd_b).min()),
            "dd_shallower": float((dd > dd_b).mean()), "dca_dd_median": float(np.median(dd_b)), "dca_dd_worst": float(dd_b.min()),
            "edges": e, "start_dates": np.array(starts)}


def _trend_state(index, ma: int, band: float) -> np.ndarray:
    """True while a total-return index is in an uptrend: on above its ``ma``-day average by ``band``, off below it by
    ``band``, unchanged in between."""
    avg = index.rolling(ma).mean()
    up, dn = (index > avg * (1 + band)).to_numpy(), (index < avg * (1 - band)).to_numpy()
    out = np.zeros(len(index), dtype=bool)
    state = False
    for i in range(len(index)):
        if up[i]:
            state = True
        elif dn[i]:
            state = False
        out[i] = state
    return out


@dataclass(frozen=True)
class Parity:
    """Trend-following risk parity with leverage: the mega strategy.

    Each asset (stocks, 10-year Treasuries, gold) is held only while it is above its own ``ma``-day average. Held
    assets share the risk in the proportions ``risk`` (stocks, bonds, gold): weight = share / the asset's volatility
    (last ``vol_days`` days). The whole book is then scaled so that its volatility (from the held assets' last
    ``vol_days`` days of joint returns) is ``target`` a year, up to ``max_gross`` x the account (3x: what 3x funds
    allow, no margin loan). ``ndx``: share of the stock sleeve in the Nasdaq-100. What is not invested earns T-bills;
    leverage pays the bill rate + ``spread`` and the funds' ``fee`` on the leveraged part. Re-sized when a trend
    flips or the book is off by more than ``rebalance``."""

    target: float = 0.15
    max_gross: float = 3.0
    risk: tuple = (0.5, 0.3, 0.2)
    ma: int = 200
    band: float = 0.01
    vol_days: int = 63
    ndx: float = 0.0
    rebalance: float = 0.15
    spread: float = 0.005
    fee: float = 0.0095
    cost: float = 0.001
    lag: int = 2

    def sleeves(self, a):
        import pandas as pd

        ndx = a["ndx"].where(a["ndx"].notna(), a["spx"])
        stock = (1.0 - self.ndx) * a["spx"] + self.ndx * ndx
        return pd.DataFrame({"stock": stock, "bond": a["bond"], "gold": a["gold"]}, index=a.index)

    def weights(self, a):
        """Held weights of ``stock, bond, gold`` (their sum is the gross exposure), already lagged."""
        import pandas as pd

        r = self.sleeves(a)
        cols = list(r.columns)
        on = np.column_stack([_trend_state((1.0 + r[c].fillna(0.0)).cumprod(), self.ma, self.band) & r[c].notna().to_numpy()
                              for c in cols])
        on[:, 0] = _trend_state(a["px"], self.ma, self.band)             # stocks: the S&P 500's own trend
        vol = np.column_stack([(r[c].rolling(self.vol_days).std() * np.sqrt(252)).to_numpy() for c in cols])
        raw = np.where(on & (vol > 0), np.array(self.risk) / np.where(vol > 0, vol, 1.0), 0.0)
        raw = np.nan_to_num(raw)
        # the book's volatility at these weights, from the joint returns of the last vol_days days
        x = r.fillna(0.0).to_numpy()
        want = np.zeros_like(raw)
        n = self.vol_days
        for i in range(n, len(r)):
            w = raw[i]
            if not w.any():
                continue
            pv = (x[i - n + 1:i + 1] @ w).std() * np.sqrt(252)
            if pv <= 0:
                continue
            w = w * self.target / pv
            g = w.sum()
            want[i] = w * min(1.0, self.max_gross / g)
        held = np.zeros_like(want)
        h = np.zeros(len(cols))
        for i in range(len(r)):
            w = want[i]
            if ((w > 0) != (h > 0)).any() or np.abs(w - h).sum() > self.rebalance * max(h.sum(), 1e-9):
                h = w
            held[i] = h
        return pd.DataFrame(held, index=a.index, columns=cols).shift(self.lag).fillna(0.0)

    def returns(self, a):
        w = self.weights(a)
        r = self.sleeves(a).fillna(0.0)
        gross = w.sum(axis=1)
        d = a["days"]
        lev = (gross - 1.0).clip(lower=0.0)
        out = ((w * r).sum(axis=1) + (1.0 - gross).clip(lower=0.0) * a["bill"]
               - lev * (a["bill"] + self.spread * d / 365.0) - lev / 2.0 * self.fee * d / 365.0)
        traded = w.diff().abs().sum(axis=1).fillna(0.0)
        return out - traded * self.cost, w
