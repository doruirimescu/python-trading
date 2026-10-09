"""Search for a durable edge vs the S&P 500 (SPY), 2000 → 2026.

Research harness behind the "Sector Trend" page. Usage (from Trading/basket):
    python3 research/edge_research.py                        # country ETFs, Treasuries as risk-off
    UNIVERSE=sectors RISKOFF=VFITX python3 research/edge_research.py
    UNIVERSE=sectors RISKOFF=CASH SMA_M=12 python3 research/edge_research.py
Prices are downloaded once into research/px.pkl; outputs go next to this file.

All strategies use textbook parameters fixed in advance (no tuning), signals at
month-end close executed at the next close (1-day lag), 5 bps per side.
A strategy is "durable" only if it holds up in both halves: 2000–2012, 2013–2026.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
BASKET = HERE.parent
sys.path.insert(0, str(BASKET / "src"))

import os
UNIVERSES = {"countries": ["EWG", "EWQ", "EWU", "EWJ", "EWC", "EWA", "EWL", "EWN", "EWD"],
             "sectors": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB"]}
UNI = os.environ.get("UNIVERSE", "countries")
COUNTRIES = UNIVERSES[UNI]
BOND = os.environ.get("RISKOFF", "VFITX")
SMA_M = int(os.environ.get("SMA_M", 10))  # VFITX (bonds) or CASH
COST = 5e-4
START, H1_END, H2_START = "2000-01-03", "2012-12-31", "2013-01-01"

PX = HERE / "px.pkl"
if not PX.exists():
    import yfinance as yf
    tickers = ["SPY", "VFITX", "^IRX"] + [t for u in UNIVERSES.values() for t in u]
    yf.download(tickers, start="1998-01-01", end="2026-10-09", auto_adjust=True, progress=False)["Close"].to_pickle(PX)
px = pd.read_pickle(PX).ffill()
px = px[px.index >= "1998-01-02"]
R = px.pct_change().fillna(0.0)
R["CASH"] = (px["^IRX"].ffill() / 100.0 / 252.0).shift(1).fillna(0.0)
dates = px.index
month_end = pd.Series(dates, index=dates).groupby(dates.to_period("M")).last().values
is_me = dates.isin(month_end)


def simulate(target: pd.DataFrame, lag: int = 1) -> pd.Series:
    """Daily equity from target weights (rows = signal dates; NaN rows = hold).

    Weights drift with returns between rebalances; turnover pays COST.
    """
    cols = list(target.columns)
    tgt = target.reindex(dates).shift(lag)  # executed `lag` closes after the signal
    rets = R[cols].values
    w = np.zeros(len(cols))
    eq = np.empty(len(dates))
    v = 1.0
    for i in range(len(dates)):
        if i:
            g = rets[i] * w
            v *= 1.0 + g.sum()
            w = w * (1.0 + rets[i])
            s = w.sum()
            w = w / s if s > 0 else w
        row = tgt.values[i]
        if not np.isnan(row).all():
            new = np.nan_to_num(row)
            v *= 1.0 - COST * np.abs(new - w).sum()
            w = new
        eq[i] = v
    return pd.Series(eq, index=dates)


def stats(eq: pd.Series, a: str, b: str) -> dict:
    e = eq[(eq.index >= a) & (eq.index <= b)]
    e = e / e.iloc[0]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    cash = R["CASH"].reindex(r.index)
    ex = r - cash
    dd = (e / e.cummax() - 1).min()
    cagr = e.iloc[-1] ** (1 / yrs) - 1
    return dict(cagr=cagr, vol=r.std() * np.sqrt(252), sharpe=ex.mean() / ex.std() * np.sqrt(252), mdd=dd,
                calmar=cagr / -dd if dd < 0 else np.nan)


def monthly(fn) -> pd.DataFrame:
    """Build a target-weight frame by calling fn(i) at each month-end index i."""
    rows = {}
    for i in np.where(is_me)[0]:
        rows[dates[i]] = fn(i)
    return pd.DataFrame(rows).T


ME = px  # month-end prices are px at month-end rows
cols_all = list(dict.fromkeys(COUNTRIES + ["SPY", "VFITX", "CASH"]))


def zeros():
    return pd.Series(0.0, index=cols_all)


def sma10m(sym, i):
    """Price vs its 10-month SMA of month-end closes, using data up to bar i."""
    me_idx = np.where(is_me[: i + 1])[0][-SMA_M:]
    if len(me_idx) < SMA_M:
        return None
    return px[sym].iloc[i] > px[sym].iloc[me_idx].mean()


def ret_lb(sym, i, months, skip=0):
    me_idx = np.where(is_me[: i + 1])[0]
    if len(me_idx) < months + 1:
        return None
    a, b = me_idx[-1 - months], me_idx[-1 - skip]
    return px[sym].iloc[b] / px[sym].iloc[a] - 1


def cash_12m(i):
    me_idx = np.where(is_me[: i + 1])[0]
    a = me_idx[-13] if len(me_idx) >= 13 else 0
    return float(np.prod(1 + R["CASH"].iloc[a + 1: i + 1]) - 1)


strategies = {}

# S0  SPY buy & hold (benchmark)
strategies["SPY buy & hold"] = monthly(lambda i: zeros().where(zeros().index != "SPY", 1.0))

# S1  Equal-weight 9 countries, monthly rebalance
strategies["EW universe"] = monthly(lambda i: zeros().where(~zeros().index.isin(COUNTRIES), 1 / 9))


# S2  SPY with 10-month SMA filter → bonds
def s2(i):
    w = zeros()
    up = sma10m("SPY", i)
    w["SPY" if (up is None or up) else BOND] = 1.0
    return w
strategies["SPY + trend"] = monthly(s2)


# S3  GTAA countries: each 1/9 if above 10m SMA, else that slice in bonds
def s3(i):
    w = zeros()
    for c in COUNTRIES:
        up = sma10m(c, i)
        w[c if (up is None or up) else BOND] += 1 / 9
    return w
strategies["Universe + trend"] = monthly(s3)


# S4  Country momentum: top 3 by 12-1 month return, equal weight
def top3(i):
    m = {c: ret_lb(c, i, 12, 1) for c in COUNTRIES}
    if any(v is None for v in m.values()):
        return COUNTRIES[:3], m
    return sorted(COUNTRIES, key=lambda c: -m[c])[:3], m
def s4(i):
    w = zeros()
    for c in top3(i)[0]:
        w[c] = 1 / 3
    return w
strategies["Momentum top-3"] = monthly(s4)


# S5  Dual momentum: top 3, each slot only if its 12m return beats cash, else bonds
def s5(i):
    w = zeros()
    sel, _ = top3(i)
    hurdle = cash_12m(i)
    for c in sel:
        r12 = ret_lb(c, i, 12)
        w[c if (r12 is None or r12 > hurdle) else BOND] += 1 / 3
    return w
strategies["Dual momentum top-3"] = monthly(s5)


# S6  Dual momentum with SPY in the candidate set
def s6(i):
    w = zeros()
    pool = COUNTRIES + ["SPY"]
    m = {c: ret_lb(c, i, 12, 1) for c in pool}
    sel = pool[:3] if any(v is None for v in m.values()) else sorted(pool, key=lambda c: -m[c])[:3]
    hurdle = cash_12m(i)
    for c in sel:
        r12 = ret_lb(c, i, 12)
        w[c if (r12 is None or r12 > hurdle) else BOND] += 1 / 3
    return w
strategies["Dual momentum top-3 (+SPY)"] = monthly(s6)


# S7/S8  mrscore mean-reversion rotation, ensemble over ALL 840 ratios (no selection)
def mr_ensemble_weights():
    from mrscore.app.composition_root import build_app
    from mrscore.config.loader import load_config
    from mrscore.core.ratio_universe import RatioUniverse
    from mrscore.io.adapters import AlignedPanel
    from mrscore.cli.main_2 import _job_to_ratio_spec

    cache = HERE / f"mr_weights_{UNI}.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    cfg = load_config(BASKET / "config_2000.yaml")
    app = build_app(cfg)
    sub = px.loc[px.index >= "1999-06-01", COUNTRIES]
    panel = AlignedPanel(dates=sub.index.values, symbols=COUNTRIES, values=sub.values.copy())
    ru = RatioUniverse(panel=panel, normalize_by_first=True, eps=1e-12)
    rc = cfg.ratio_universe
    jobs = list(ru.iter_ratio_jobs(k_num=rc.k_num, k_den=rc.k_den, unordered_if_equal_k=rc.unordered_if_equal_k,
                                   disallow_overlap=rc.disallow_overlap))
    T, N = sub.shape
    W = np.zeros((T, N))
    for job in jobs:
        spec, _ = _job_to_ratio_spec(ru, job)
        res = app.backtester.run_one(panel=panel, ratio_spec=spec, job_id="")
        for tr in res.trades:
            idx = spec.numerator.indices if tr.direction.value == "up" else spec.denominator.indices
            W[tr.entry_index: tr.exit_index, idx] += 1.0 / len(idx)  # held from entry close to exit close
    W /= len(jobs)
    out = pd.DataFrame(W, index=sub.index, columns=COUNTRIES)
    out.to_pickle(cache)
    return out


mrw = mr_ensemble_weights()
mr_full = pd.DataFrame(0.0, index=mrw.index, columns=cols_all)
mr_full[COUNTRIES] = mrw.values
mr_full["CASH"] = 1.0 - mr_full[COUNTRIES].sum(axis=1)  # warm-up / unallocated → cash
strategies["MR rotation, all-840 ensemble"] = mr_full  # daily targets

# Trend state is decided at month-end (as in S3) and held for the month.
me_px = px.loc[is_me, COUNTRIES]
up_daily = (me_px > me_px.rolling(SMA_M).mean()).where(me_px.rolling(SMA_M).count() == SMA_M).reindex(dates).ffill()
filt = mr_full.copy()
for c in COUNTRIES:
    off = ~up_daily[c].reindex(filt.index).fillna(True).astype(bool)
    filt.loc[off, BOND] += filt.loc[off, c]
    filt.loc[off, c] = 0.0
strategies["MR ensemble + trend"] = filt

spy_tr_daily = strategies["SPY + trend"].reindex(dates).ffill().fillna(0.0)
blend = 0.5 * spy_tr_daily.reindex(filt.index).fillna(0.0) + 0.5 * filt
strategies["50/50 SPY-trend + MR-trend"] = blend

# --------------------------------------------------------------------- report
res = {}
for name, tgt in strategies.items():
    eq = simulate(tgt)
    res[name] = eq
pd.DataFrame(res).to_pickle(HERE / f"edge_equity_{UNI}_{BOND}_{SMA_M}.pkl")

hdr = f"{'strategy':32s} | {'FULL 2000–2026':^34s} | {'2000–2012':^16s} | {'2013–2026':^16s}"
print(hdr); print(f"{'':32s} | {'CAGR':>7s} {'MaxDD':>7s} {'Sharpe':>6s} {'Calmar':>6s} | {'CAGR':>7s} {'MaxDD':>7s} | {'CAGR':>7s} {'MaxDD':>7s}")
for name, eq in res.items():
    f, a, b = stats(eq, START, "2026-10-08"), stats(eq, START, H1_END), stats(eq, H2_START, "2026-10-08")
    print(f"{name:32s} | {f['cagr']:+7.2%} {f['mdd']:7.1%} {f['sharpe']:6.2f} {f['calmar']:6.2f} | {a['cagr']:+7.2%} {a['mdd']:7.1%} | {b['cagr']:+7.2%} {b['mdd']:7.1%}")
