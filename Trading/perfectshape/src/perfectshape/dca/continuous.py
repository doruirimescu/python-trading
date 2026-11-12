"""The combined strategy: a continuous borrowing function of the trend, the VIX, the borrowing rate and the bill
rate, fitted on history. The account never sells: it only borrows more or less, and payments repay the debt.

**The function** (Merton's portfolio rule with different borrowing and lending rates). Each day, from the previous
close:

    expected return   mu = y10 + p0 + p1 * tanh((S&P / 200-day average - 1) / 0.05) - a * (6-month rise of y10)
                           + b * (y10 - y3m)
    variance          s2 = (VIX / 100) ** 2            (realised volatility x the VIX premium before 1990)
    borrow side       E_b = k * (mu - y10 - spread) / s2     stocks vs the margin rate
    lend side         E_l = k * (mu - y3m) / s2              stocks vs T-bills

    exposure target   E_b if E_b > 1 (borrow);  E_l if E_l < 1 (hold payments in cash);  1 otherwise (plain DCA)

clipped to [0, 2]. ``k`` is the Kelly fraction (how much of the theoretically optimal bet to take). Without selling,
the account reaches a higher target by buying with borrowed money and a lower one by keeping payments in cash; debt
is capped at ``max_debt`` payments (what the payments can repay) and cash at ``max_cash`` payments.

``fit()`` chooses the parameters on 10-year accounts that start and end in 1962-1999 (a penalised median edge over
plain DCA, see :func:`objective`); 2000-2026 and 1928-1961 stay untouched for the test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from functools import lru_cache

import numpy as np

from perfectshape.dca.exposure import ExposureConfig, simulate_exposure
from perfectshape.dca.policy import lagged
from perfectshape.dca.rules import Rule


@dataclass(frozen=True)
class Combined:
    p0: float = 0.00          # expected return over the 10-year yield when the index is at its average (a year)
    p1: float = 0.05          # + p1 well above the average, - p1 well below (smooth: tanh of distance / 5%)
    a: float = 0.03           # expected return lost per point the 10-year yield rose over the last 6 months
    b: float = 0.0            # expected return per point of yield curve (10-year minus 3-month)
    k: float = 0.3            # Kelly fraction
    max_debt: int = 24        # payments of debt at most
    max_cash: int = 0         # payments held in cash at most
    spread: float = 0.0       # margin rate = 10-year yield + this

    def expected(self, g):
        """Expected S&P 500 return a year (decimal) on yesterday's signals ``g``."""
        y10 = g["y10"] / 100.0
        trend = np.tanh(g["trend"].fillna(0.0) / 0.05)
        rise = g["y10_chg"].fillna(0.0)
        curve = g["curve"].fillna(0.0)
        return y10 + self.p0 + self.p1 * trend - self.a * rise + self.b * curve

    def target(self, f):
        """Exposure target per day (a pandas Series on ``f``'s index)."""
        g = lagged(f)
        mu = self.expected(g)
        s2 = (g["vix_like"].bfill().ffill() / 100.0) ** 2
        e_b = self.k * (mu - g["y10"] / 100.0 - self.spread) / s2
        e_l = self.k * (mu - g["y3m"].fillna(0.0) / 100.0) / s2
        e = e_b.where(e_b > 1.0, e_l.where(e_l < 1.0, 1.0))
        if self.max_cash <= 0:
            e = e.clip(lower=1.0)
        return e.clip(0.0, 2.0).fillna(1.0)

    def rule(self) -> Rule:
        return Rule("Combined: continuous borrowing (VIX, rates, trend), never sells", self.target, False, "combined")

    def account(self, **kw) -> ExposureConfig:
        return ExposureConfig(max_debt=float(self.max_debt), max_cash=float(self.max_cash), borrow_spread=self.spread, **kw)


# ---------------------------------------------------------------- fitting

TRAIN = ("1962-01-01", "1999-12-31")
BOUNDS = [(-0.10, 0.10), (0.0, 0.20), (0.0, 0.15), (-0.03, 0.03), (0.0, 1.0), (6, 60), (0, 6)]
NAMES = ("p0", "p1", "a", "b", "k", "max_debt", "max_cash")


def from_vector(x) -> Combined:
    return Combined(float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), int(round(x[5])), int(round(x[6])))


@lru_cache(maxsize=1)
def _train_setup():
    from perfectshape.dca.data import load_market
    from perfectshape.dca.evaluate import windows
    from perfectshape.dca.signals import features

    m = load_market()
    f = features(m)
    dates = m.index.values.astype("datetime64[D]")
    w = windows(dates, 10, TRAIN[0], TRAIN[1], step=3)
    args = (m["tr"].to_numpy(), dates)
    rates = (m["y10"].to_numpy(), m["y3m"].to_numpy())
    base = simulate_exposure(*args, np.ones(len(dates)), *rates, ExposureConfig(), False, w.starts, w.ends)
    return f, args, rates, w, base


def evaluate_train(c: Combined) -> dict:
    f, args, rates, w, base = _train_setup()
    res = simulate_exposure(*args, np.asarray(c.target(f), dtype=float), *rates, c.account(), False, w.starts, w.ends)
    edge = res["wealth"] / base["wealth"] - 1.0
    dd = res["max_dd"] - base["max_dd"]
    return {"median": float(np.median(edge)), "worst": float(edge.min()), "win": float((edge > 0).mean()),
            "p10": float(np.quantile(edge, 0.1)), "dd": float(np.median(dd)), "dd_worst": float(dd.min()),
            "calls": int(res["margin_calls"].sum())}


def objective(x) -> float:
    """Minimised: -(median edge) with penalties: worst account below -3%, median fall more than 2 points deeper than
    plain DCA's, worst fall more than 8 points deeper, any margin call."""
    r = evaluate_train(from_vector(x))
    pen = (5.0 * max(0.0, -0.03 - r["worst"]) + 3.0 * max(0.0, -0.02 - r["dd"]) + 2.0 * max(0.0, -0.08 - r["dd_worst"])
           + 0.05 * r["calls"])
    return -(r["median"] - pen)


def fit(maxiter: int = 25, popsize: int = 10, workers: int = -1, seed: int = 7):
    from scipy.optimize import differential_evolution

    res = differential_evolution(objective, BOUNDS, integrality=[False] * 5 + [True, True], maxiter=maxiter,
                                 popsize=popsize, workers=workers, updating="deferred", seed=seed, polish=False, tol=1e-4)
    return from_vector(res.x), res


def estimate_expected(m, f, first: str, last: str) -> dict:
    """The expected-return equation by least squares instead of by optimising wealth: the S&P 500's return over the
    10-year yield in each calendar month (annualised), on the signals of the last close before the month, for months
    in [first, last]. Returns p0, p1, a, b and their t-statistics."""
    import pandas as pd

    r = m["tr"].pct_change()
    days = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1)
    ex = r - m["y10"] / 100.0 * days / 365.0
    g = f.shift(1)                                              # signals of the previous close
    month = m.index.to_period("M")
    df = pd.DataFrame({"ex": ex, "x1": np.tanh(g["trend"] / 0.05), "x2": g["y10_chg"], "x3": g["curve"]}, index=m.index)
    mon = df.groupby(month).agg(ex=("ex", "sum"), x1=("x1", "first"), x2=("x2", "first"), x3=("x3", "first")).dropna()
    mon = mon[(mon.index >= pd.Period(first[:7], "M")) & (mon.index <= pd.Period(last[:7], "M"))]
    X = np.column_stack([np.ones(len(mon)), mon["x1"], -mon["x2"], mon["x3"]])
    y = mon["ex"].to_numpy() * 12.0
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    cov = np.linalg.inv(X.T @ X) * (resid @ resid) / max(len(y) - X.shape[1], 1)
    t = beta / np.sqrt(np.diag(cov))
    return {"p0": float(beta[0]), "p1": float(beta[1]), "a": float(beta[2]), "b": float(beta[3]),
            "t": {k: float(v) for k, v in zip(("p0", "p1", "a", "b"), t)}, "months": int(len(y)), "first": first, "last": last}


def fit_sizing(est: dict, grid_k=(0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0), grid_debt=(6, 12, 18, 24, 36),
               grid_cash=(0, 3, 6)) -> tuple["Combined", list[dict]]:
    """With the expected-return equation fixed, choose the Kelly fraction and the caps on 1962-1999 by the same
    penalised objective as :func:`objective`."""
    rows = []
    for k in grid_k:
        for d in grid_debt:
            for c in grid_cash:
                x = [est["p0"], est["p1"], est["a"], est["b"], k, d, c]
                rows.append({"k": k, "max_debt": d, "max_cash": c, "score": -objective(x), **evaluate_train(from_vector(x))})
    best = max(rows, key=lambda r: r["score"])
    return from_vector([est["p0"], est["p1"], est["a"], est["b"], best["k"], best["max_debt"], best["max_cash"]]), rows


def describe(c: Combined) -> dict:
    return {**asdict(c)}


__all__ = ["Combined", "fit", "objective", "evaluate_train", "from_vector", "describe", "replace", "Kelly",
           "estimate_kelly_forecast", "month_table", "ERAS"]


# ---------------------------------------------------------------- the robust version: Kelly sizing on coarse forecasts

ERAS = {"1928-1961": ("1928-01-01", "1961-12-31"), "1962-1999": ("1962-01-01", "1999-12-31"),
        "2000-today": ("2000-01-01", "2100-01-01")}


@dataclass(frozen=True)
class Kelly:
    """Merton / Kelly sizing on the forecasts that held in every era: the excess return of the S&P 500 over the
    10-year yield is ``p_above`` well above the 200-day average and ``p_below`` well below it (smooth in between, over
    about ``width`` of distance), minus ``a`` per point the 10-year yield rose over 6 months. Variance from the VIX.
    Borrow when k x (expected - margin rate) / variance > 1, hold payments when k x (expected - bill rate) / variance
    < 1. Never sells; debt and cash capped in payments."""

    p_above: float = 0.09
    p_below: float = 0.01
    a: float = 0.05
    k: float = 0.2
    max_debt: int = 18
    max_cash: int = 3
    width: float = 0.02
    spread: float = 0.0

    def expected(self, g):
        w = 0.5 * (1.0 + np.tanh(g["trend"].fillna(0.0) / self.width))
        return (g["y10"] / 100.0 + self.p_below + (self.p_above - self.p_below) * w
                - self.a * g["y10_chg"].fillna(0.0))

    def target(self, f):
        g = lagged(f)
        mu = self.expected(g)
        s2 = (g["vix_like"].bfill().ffill() / 100.0) ** 2
        e_b = self.k * (mu - g["y10"] / 100.0 - self.spread) / s2
        e_l = self.k * (mu - g["y3m"].fillna(0.0) / 100.0) / s2
        e = e_b.where(e_b > 1.0, e_l.where(e_l < 1.0, 1.0))
        if self.max_cash <= 0:
            e = e.clip(lower=1.0)
        return e.clip(0.0, 2.0).fillna(1.0)

    def rule(self) -> Rule:
        return Rule("Combined: Kelly borrowing on VIX, rates and trend, never sells", self.target, False, "combined")

    def account(self, **kw) -> ExposureConfig:
        return ExposureConfig(max_debt=float(self.max_debt), max_cash=float(self.max_cash), borrow_spread=self.spread, **kw)


def month_table(m, f):
    """Per calendar month: the S&P 500's return over the 10-year yield (annualised) and the signals of the last close
    before it."""
    import pandas as pd

    r = m["tr"].pct_change()
    days = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1)
    ex = r - m["y10"] / 100.0 * days / 365.0
    g = f.shift(1)
    df = pd.DataFrame({"ex": ex, "trend": g["trend"], "rise": g["y10_chg"]}, index=m.index)
    mon = df.groupby(m.index.to_period("M")).agg(ex=("ex", "sum"), trend=("trend", "first"), rise=("rise", "first")).dropna()
    mon["ex"] *= 12.0
    return mon


def estimate_kelly_forecast(mon, eras: list[str]) -> dict:
    """p_above, p_below: mean excess return of months starting above / below the average; a: slope of the excess
    return on the 6-month yield rise (with the trend state held fixed). Only months of ``eras``."""
    import pandas as pd

    keep = np.zeros(len(mon), dtype=bool)
    for e in eras:
        a, b = ERAS[e]
        keep |= (mon.index >= pd.Period(a[:7], "M")) & (mon.index <= pd.Period(b[:7], "M"))
    x = mon[keep]
    above = x["trend"] > 0
    X = np.column_stack([above.astype(float), (~above).astype(float), -x["rise"]])
    beta, *_ = np.linalg.lstsq(X, x["ex"].to_numpy(), rcond=None)
    return {"p_above": float(beta[0]), "p_below": float(beta[1]), "a": float(beta[2]), "months": int(len(x)), "eras": list(eras)}
