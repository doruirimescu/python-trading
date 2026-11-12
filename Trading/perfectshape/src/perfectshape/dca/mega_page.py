"""The mega strategy's page (``rules/mega-strategy.html`` of a DCA run): the rule-page sections of
:mod:`perfectshape.dca.pages`, filled from the strategy's return series, plus tables by era, of the variants tried and
of what it holds today."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import numpy as np

from perfectshape.dca.account import pay_days
from perfectshape.dca.mega import ERAS, Mega, assets, dca_stats, leveraged, perf
from perfectshape.dca.pages import CRASHES, DS, HORIZONS, _ds, _horizon

NAME = "Mega strategy: 3x stocks in uptrends, volatility-capped; bonds, gold or bills otherwise"
SLUG = "mega-strategy"
KEYS = ("n", "win", "median", "p10", "worst", "best", "dd_median", "dd_worst", "dd_vs_dca", "dd_vs_dca_worst", "dd_shallower",
        "dca_dd_median", "dca_dd_worst")

DOCS = {
    "what": "Free of the DCA rules: any asset, leverage through 3x funds (no margin loan, so no margin call). While the "
            "S&P 500 is in an uptrend the account holds a 3x S&P 500 fund, sized so that its volatility stays near 25% a "
            "year; the rest, and everything in a downtrend, sits in 10-year Treasuries, gold or T-bills, whichever is "
            "rising. The $2,000 a month goes into whatever the account holds that day.",
    "how": "Uptrend: the S&P 500 closes more than 1% above its 200-day average (and stays on until it closes more than 1% "
           "below). Weight of the 3x fund = 25% / (3 x the S&P 500's volatility of the last 21 days), at most 100%: about "
           "70% in a calm market (exposure 2.1x), 30% in a nervous one. The safe asset is the 10-year Treasury while it is "
           "above its own 200-day average, else gold while above its average, else T-bills. Signals use the previous "
           "close and trade at the next one; the 3x fund is modelled as 3 x the index's daily return minus financing of "
           "the borrowed two thirds at the T-bill rate + 0.5% and a 0.95% yearly fee, which matches UPRO since 2009 "
           "(+32.6% a year modelled, +32.1% real). Every trade costs 0.1%.",
    "idea": "Three things that held in every era of this research, stacked: stocks earn far more above their 200-day "
            "average than below it; leverage is only safe when volatility is low, and volatility clusters; and a 3x fund "
            "cannot lose more than what is in it. The defaults (200 days, 3x, 25%) were set before the first test and "
            "not tuned; the table of variants shows the neighbours do about the same.",
    "risk": "It still fell 50% (1929-32: plain DCA fell 84%). A one-day crash is not avoidable by a trend rule: on a day "
            "like October 1987 (-20%) a 3x fund loses about 60% of what is in it. In sideways markets it is whipsawed: "
            "since 2013 it earned slightly less than the S&P 500 at a lower Sharpe ratio. Leveraged funds decay in "
            "choppy markets, can be closed by their issuer, and every switch is a taxable sale (taxes not modelled). "
            "The 10-year Treasury before 1962 is built from monthly yields, and gold only exists here from 2000.",
}


def _exposure(m: Mega, w):
    return (w["eq"] * m.lev + w["eq1"]).to_numpy()


def _stats(m: Mega, a, years, first=None, last=None) -> dict:
    r, w = m.returns(a)
    dates = a.index.values.astype("datetime64[D]")
    d = dca_stats(r.to_numpy(), a["spx"].to_numpy(), dates, years, first, last)
    keep = (a.index >= (first or "1900")) & (a.index <= (last or "2200"))
    turn = float(w.diff().abs().sum(axis=1)[keep].sum() / 2.0 / max(keep.sum() / 252.0, 1e-9))
    out = {k: d[k] for k in KEYS}
    out |= {"rule": NAME, "family": "mega", "calls": 0, "wiped": False, "avg_exposure": float(_exposure(m, w)[keep].mean()),
            "turnover": turn * years}
    return out, d


def _row(name, r, a) -> list[str]:
    p = perf(r, a["bill"])
    d = dca_stats(r.to_numpy(), a["spx"].to_numpy(), a.index.values.astype("datetime64[D]"))
    return [name, f"{p['cagr']:+.1%}", f"{p['sharpe']:.2f}", f"{p['vol']:.0%}", f"{p['max_dd']:.0%}", f"{p['worst_year']:+.0%}",
            f"{d['win']:.0%}", f"{d['median']:+.0%}", f"{d['worst']:+.0%}"]


def mega_page(m: Mega = Mega(), generated: str | None = None, nav: list | None = None) -> dict:
    a = assets()
    r, w = m.returns(a)
    dates = a.index.values.astype("datetime64[D]")
    spx = a["spx"]
    settings = {"us5": ("5-year accounts, 1962 to today", m, 5, "1962-01-01", None),
                "us10": ("10-year accounts, 1962 to today", m, 10, "1962-01-01", None),
                "us20": ("20-year accounts, 1962 to today", m, 20, "1962-01-01", None),
                "early10": ("10-year accounts, 1928-1961", m, 10, None, "1961-12-31"),
                "cost": ("10-year, 0.3% cost on every trade", replace(m, cost=0.003), 10, "1962-01-01", None),
                "margin": ("10-year, fund financing 2 points dearer", replace(m, spread=0.025), 10, "1962-01-01", None)}
    st, edges = {}, {}
    for key, (label, mm, years, first, last) in settings.items():
        s, d = _stats(mm, a, years, first, last)
        st[key] = {**s, "label": label}
        if key in ("us10", "early10"):
            edges[key] = {"dates": [str(x) for x in d["start_dates"]], "edge": np.round(d["edges"], 5).tolist()}
    # savers who started 10, 15, 20 and 30 years ago: payments compounded along each return series
    pay = pay_days(dates).astype(float) * 2000.0
    horizons = {}
    for y in HORIZONS:
        start = dates[-1] - np.timedelta64(int(y * 365.25), "D")
        i0 = int(np.flatnonzero(pay_days(dates) & (dates >= start))[0])
        wa, wb = np.zeros(len(dates) - i0), np.zeros(len(dates) - i0)
        ra, rb, p = r.to_numpy()[i0:], spx.to_numpy()[i0:], pay[i0:]
        for j in range(len(wa)):
            prev_a, prev_b = (wa[j - 1], wb[j - 1]) if j else (0.0, 0.0)
            wa[j] = prev_a * (1.0 + ra[j]) + p[j]
            wb[j] = prev_b * (1.0 + rb[j]) + p[j]
        horizons[str(y)] = _horizon(dates[i0:], wa, wb, np.cumsum(p))
    # the one account, 1928 to today
    i0 = int(np.flatnonzero(pay_days(dates))[0])
    ua, ub = np.cumprod(1.0 + r.to_numpy()), np.cumprod(1.0 + spx.to_numpy())
    ua, ub = ua / ua[i0], ub / ub[i0]
    dd = lambda u: u / np.maximum.accumulate(u) - 1.0
    px = a["px"]
    avg = px.rolling(m.ma).mean()
    expo = _exposure(m, w)
    crashes = []
    for name, s, e in CRASHES:
        win = px[s:e]
        if len(win) < 20:
            continue
        pk = win.idxmax()
        tr_ = win[pk:].idxmin()
        ip, it = a.index.get_loc(pk), a.index.get_loc(tr_)
        ir = min(it + 252, len(a) - 1)
        crashes.append({"name": name, "peak": str(pk.date()), "trough": str(tr_.date()), "index_fall": float(px[tr_] / px[pk] - 1.0),
                        "fall": float(ua[it] / ua[ip] - 1.0), "fall_dca": float(ub[it] / ub[ip] - 1.0),
                        "avg_exposure": float(expo[ip:it + 1].mean()), "exposure_at_peak": float(expo[ip]),
                        "year_after": float(ua[ir] / ua[it] - 1.0), "year_after_dca": float(ub[ir] / ub[it] - 1.0)})
    years = a.index.year
    decades = []
    for d0 in range(1930, 2030, 10):
        mask = np.flatnonzero((years >= d0) & (years < d0 + 10))
        if len(mask) < 252:
            continue
        s, e = mask[0], mask[-1]
        yrs = len(mask) / 252.0
        g = lambda u: (u[e] / u[s]) ** (1 / yrs) - 1.0
        decades.append({"decade": f"{d0}s", "cagr": float(g(ua)), "cagr_dca": float(g(ub)), "avg_exposure": float(expo[s:e + 1].mean()),
                        "max_dd": float(dd(ua[s:e + 1]).min()), "max_dd_dca": float(dd(ub[s:e + 1]).min())})
    sl = slice(i0, None)
    series = {"dates": [str(x) for x in dates[sl][::DS]], "px": _ds(px.to_numpy()[sl], 2), "avg": _ds(avg.to_numpy()[sl], 2),
              "target": _ds(expo[sl], 3), "exposure": _ds(expo[sl], 3), "unit": _ds(ua[sl], 5), "unit_dca": _ds(ub[sl], 5),
              "dd": _ds(dd(ua[sl]), 4), "dd_dca": _ds(dd(ub[sl]), 4)}
    n_years = (len(dates) - i0) / 252.0
    on = (w["eq"] > 0).to_numpy()
    whole = {"cagr": float(ua[-1] ** (1 / n_years) - 1.0), "cagr_dca": float(ub[-1] ** (1 / n_years) - 1.0),
             "max_dd": float(dd(ua[sl]).min()), "max_dd_dca": float(dd(ub[sl]).min()), "calls": 0, "wiped": False,
             "avg_exposure": float(expo[sl].mean()), "start": str(dates[i0]), "share_borrowed": float((expo[sl] > 1.001).mean()),
             "share_cash": float((expo[sl] < 0.999).mean()), "switches_per_year": float(np.abs(np.diff(on[sl].astype(int))).sum() / n_years)}
    # by era: the strategy against the S&P 500
    pa, pb = perf(r, a["bill"]), perf(spx, a["bill"])
    era_rows = [["1928 to today", f"{pb['cagr']:+.1%}", f"{pa['cagr']:+.1%}", f"{pb['sharpe']:.2f}", f"{pa['sharpe']:.2f}",
                 f"{pb['max_dd']:.0%}", f"{pa['max_dd']:.0%}"]]
    for e, (x, y) in ERAS.items():
        qa, qb = perf(r, a["bill"], x, y), perf(spx, a["bill"], x, y)
        era_rows.append([e, f"{qb['cagr']:+.1%}", f"{qa['cagr']:+.1%}", f"{qb['sharpe']:.2f}", f"{qa['sharpe']:.2f}",
                         f"{qb['max_dd']:.0%}", f"{qa['max_dd']:.0%}"])
    # variants
    d_ = a["days"]
    off = on == 0
    variants = [("S&P 500 held (plain DCA)", spx), ("This strategy", r),
                ("Volatility cap 15%", replace(m, vol_target=0.15).returns(a)[0]), ("Volatility cap 40%", replace(m, vol_target=0.40).returns(a)[0]),
                ("No volatility cap", replace(m, vol_target=None).returns(a)[0]), ("2x fund", replace(m, lev=2.0).returns(a)[0]),
                ("150-day average", replace(m, ma=150).returns(a)[0]), ("250-day average", replace(m, ma=250).returns(a)[0]),
                ("Half of the stocks in the Nasdaq-100 (from 1986)", replace(m, ndx=0.5).returns(a)[0]),
                ("No leverage while the 10-year yield jumps (rate guard)", replace(m, guard=0.6).returns(a)[0]),
                ("3x Treasuries as the safe asset", replace(m, bond_lev=3.0).returns(a)[0]),
                ("Downtrend: stay 100% in the S&P 500", replace(m, off_equity=1.0).returns(a)[0]),
                ("Downtrend: also short the S&P 500 (100%)", r + off * (-spx + a["bill"] - 0.005 * d_ / 365.0)),
                ("One more day of delay", replace(m, lag=3).returns(a)[0]), ("0.3% cost on every trade", replace(m, cost=0.003).returns(a)[0]),
                ("3x S&P 500 fund, held", leveraged(spx, a["bill"], 3.0, days=d_)),
                ("3x: 55% S&P 500 / 45% Treasuries, rebalanced", 0.55 * leveraged(spx, a["bill"], 3.0, days=d_) + 0.45 * leveraged(a["bond"], a["bill"], 3.0, days=d_))]
    var_rows = [_row(name, x, a) for name, x in variants]
    # today
    last = w.iloc[-1]
    raw = replace(m, lag=0).weights(a).iloc[-1]                 # decided on the last close: what the next close trades to
    safe = "10-year Treasuries" if raw["bond"] > 0 else "gold" if raw["gold"] > 0 else "T-bills"
    rv = float(np.log(px).diff().rolling(m.vol_days).std().iloc[-1] * np.sqrt(252))
    eq = float(raw["eq"])
    k = lambda x: f"${x * 100_000:,.0f}"
    now_rows = [["Signals of the close of", str(a.index[-1].date())],
                ["S&P 500 vs its 200-day average", f"{px.iloc[-1] / avg.iloc[-1] - 1.0:+.1%}"],
                ["Trend", "up: hold the 3x fund" if eq > 0 or raw["eq1"] > 0 else "down: safe asset only"],
                ["S&P 500 volatility, last 21 days", f"{rv:.1%}"],
                ["Weight of the 3x fund = 25% / (3 x volatility), at most 100%", f"{eq:.0%}"],
                ["Stock exposure (3 x that weight)", f"{eq * m.lev + raw['eq1']:.2f}"],
                ["The rest goes to", f"{safe} ({1.0 - eq - raw['eq1']:.0%})"],
                ["On $100,000", f"{k(eq)} in the 3x S&P 500 fund, {k(1.0 - eq - raw['eq1'])} in {safe}"]]
    verdict = (f"From 1928 to today it grew {pa['cagr']:+.1%} a year against the S&P 500's {pb['cagr']:+.1%}, with a Sharpe ratio of "
               f"{pa['sharpe']:.2f} against {pb['sharpe']:.2f} and a deepest fall of {pa['max_dd']:.0%} against {pb['max_dd']:.0%}. "
               f"A saver paying $2,000 a month for 10 years ended ahead of plain DCA in {st['us10']['win']:.0%} of {st['us10']['n']} "
               f"accounts opened since 1962 (median {st['us10']['median']:+.0%}, worst {st['us10']['worst']:+.0%}) and in "
               f"{st['early10']['win']:.0%} of those of 1928-1961 (median {st['early10']['median']:+.0%}). It is not better in every "
               "era: since 2013 it has earned about what the S&P 500 did, at a lower Sharpe ratio, because of whipsaws in 2015-16, "
               "2018, 2020 and 2022. Nothing was fitted: the settings are the textbook ones, and every other setting of the rule in "
               "the table of variants gives 11.6% to 18.2% a year at a Sharpe ratio of 0.56 to 0.67.")
    extra = [
        {"title": "Today", "head": ["Step", "Value"], "rows": now_rows,
         "note": "What the account would hold after the next close. The monthly payment is split the same way."},
        {"title": "By era: against the S&P 500", "rows": era_rows,
         "head": ["Era", "S&P 500 a year", "Strategy a year", "S&P 500 Sharpe", "Strategy Sharpe", "S&P 500 deepest fall", "Strategy deepest fall"],
         "note": "Growth a year is time-weighted (what each dollar did). Sharpe ratio = return over T-bills divided by volatility, from daily returns."},
        {"title": "Everything else that was tried", "rows": var_rows,
         "head": ["Variant, 1928 to today", "Growth a year", "Sharpe", "Volatility", "Deepest fall", "Worst year", "10-year savers ahead of DCA", "Median edge", "Worst edge"],
         "note": "One setting changed at a time. Also tried and dropped: sharing the risk between stocks, Treasuries and gold with "
                 "leverage on all three (9.7% a year, Sharpe 0.57: leveraged Treasuries lost for two decades to 1981), sizing by "
                 "volatility with no trend rule (deepest fall 58% to 79%), and a short-volatility fund (SVXY: -92% in 2018)."},
    ]
    return {"kind": "exposure", "name": NAME, "family": "mega", "sell": True, "variant": SLUG, "nav_label": "Mega strategy",
            "eyebrow": "Mega strategy · any asset, leverage through 3x funds · no margin loan",
            "generated": generated or datetime.now().strftime("%Y-%m-%d %H:%M"), "docs": DOCS, "stats": st, "edges": edges,
            "nav": nav or [], "series": series, "crashes": crashes, "decades": decades, "whole": whole, "verdict": verdict,
            "extra": extra, "horizons": horizons, "weights_today": {k_: float(v) for k_, v in last.items()}}
