"""The DCA report: the strategy against plain DCA over every start month, the alternatives that were tried, what
each setting changes, other eras and markets, why it works, and what to do this month.

``build_payload`` -> a JSON-able dict; ``write_report`` -> ``runs/<stamp>_dca/`` with ``report.html``,
``summary.md`` and ``dca.json``.
"""

from __future__ import annotations

import html
import json
import logging
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from perfectshape.dca.account import AccountConfig, pay_days, simulate
from perfectshape.dca.data import load_early_history, load_market, load_other_market
from perfectshape.dca.evaluate import compare
from perfectshape.dca.policy import const, to_array, trend_policy, turn_of_month, when
from perfectshape.dca.signals import features
from perfectshape.dca.strategy import (EXPOSURE_RECOMMENDED, RECOMMENDED, ExposureStrategy, Strategy, decision,
                                       exposure_decision)

log = logging.getLogger(__name__)
WEB = Path(__file__).resolve().parents[1] / "web"
ERAS = [("1962-1989", "1962-01-01", "1989-12-31"), ("1990-2007", "1990-01-01", "2007-12-31"), ("2008-today", "2008-01-01", None)]
OTHER = [("^NDX", "Nasdaq-100 (price index)"), ("^GDAXI", "DAX (total return)"), ("^RUT", "Russell 2000 (price index)"),
         ("^FTSE", "FTSE 100 (price index)"), ("^N225", "Nikkei 225 (price index)")]
KEYS = ("n", "win", "median", "mean", "p10", "worst", "best", "usd_median", "usd_worst", "calls")


def _row(v: dict) -> dict:
    return {k: v[k] for k in KEYS}


def _cmp(market, pols: dict, years: int, cfg: AccountConfig, first=None, last=None, keep_edges=()):
    f = features(market)
    out = compare(market, {"dca": to_array(const(0), f), **{k: to_array(p, f) for k, p in pols.items()}}, years, cfg, first, last)
    rows = {k: _row(v) for k, v in out.items()}
    edges = {k: {"dates": [str(d) for d in out[k]["start_dates"]], "edge": np.round(out[k]["edges"], 5).tolist()}
             for k in keep_edges if k in out}
    return rows, edges


def alternatives(s: Strategy) -> dict:
    """Policies the research compared (README, "DCA"), in the order of the report's table."""
    return {
        "Hold every payment 1 month": const(1),
        "Hold 6 payments in cash": const(6),
        "Wait for a 5% dip, else hold": when(lambda g: g["dd"] < -0.05, 0, 6),
        "Always 1 payment ahead": const(-1),
        "Always 6 payments ahead": const(-6),
        "Invest 4 days before month end": turn_of_month(4),
        "Borrow after a 10% drawdown": when(lambda g: g["dd"] < -0.10, -6, 0),
        "Borrow on fear (vol spike / high VIX)": when(lambda g: (g["rv_ratio"] > 1.3) | (g["vix_pct"] > 0.8), -6, 0),
        "Borrow below the 200-day average": when(lambda g: g["trend"] < 0, -6, 0),
        "Borrow above the 200-day average (monthly)": trend_policy(s.ma, on=-s.months, monthly=True),
        "Strategy: trend + rate guard": s.policy(),
    }


def mechanism(markets: list, s: Strategy) -> list[dict]:
    """Monthly S&P 500 return over the 10-year yield by the trend state on payment day, per era."""
    import pandas as pd

    rows = []
    frames = []
    for m in markets:
        f = features(m)
        on = pd.Series(to_array(trend_policy(s.ma, monthly=True), f), index=m.index) < 0
        r = m["tr"].pct_change().fillna(0.0)
        days = pd.Series(m.index, index=m.index).diff().dt.days.fillna(1)
        ex = r - m["y10"] / 100 * days / 365
        have = f["px"].rolling(s.ma).mean().shift(1).notna()
        frames.append(pd.DataFrame({"ex": ex, "on": on})[have].groupby(m.index[have].to_period("M")).agg(ex=("ex", "sum"), on=("on", "first")))
    mon = pd.concat(frames)
    mon = mon[~mon.index.duplicated(keep="last")]
    spans = [("1928-1961", "1928", "1961"), ("1962-1989", "1962", "1989"), ("1990-2007", "1990", "2007"),
             ("2008-today", "2008", "2100"), ("All", "1900", "2100")]
    for name, a, b in spans:
        x = mon[a:b]
        if len(x) < 24:
            continue
        row = {"era": name}
        for st, lab in ((True, "above"), (False, "below")):
            v = x.loc[x["on"] == st, "ex"]
            row |= {f"{lab}_months": int(len(v)), f"{lab}_mean": float(v.mean() * 12), f"{lab}_vol": float(v.std() * np.sqrt(12)),
                    f"{lab}_t": float(v.mean() / v.std() * np.sqrt(len(v))) if len(v) > 2 else 0.0}
        rows.append(row)
    return rows


def saver_path(market, s: Strategy, start: str, cfg: AccountConfig) -> dict:
    """One saver from ``start`` to the end: wealth against plain DCA, and the cash balance."""
    f = features(market)
    dates = market.index.values.astype("datetime64[D]")
    i0 = int(np.flatnonzero(pay_days(dates) & (dates >= np.datetime64(start)))[0])
    args = (market["tr"].to_numpy(), dates)
    rates = (market["y10"].to_numpy(), market["y3m"].to_numpy())
    a = simulate(*args, to_array(s.policy(), f), *rates, cfg, starts=np.array([i0]), path=True)
    b = simulate(*args, np.zeros(len(dates)), *rates, cfg, starts=np.array([i0]), path=True)
    sl = slice(i0, None, 5)
    return {"start": str(dates[i0]), "dates": [str(d) for d in dates[sl]],
            "extra": np.round(a["wealth_path"][sl] - b["wealth_path"][sl], 0).tolist(),
            "cash": np.round(a["cash_path"][sl], 0).tolist(),
            "dca": np.round(b["wealth_path"][sl], 0).tolist(),
            "final": float(a["wealth"][0]), "final_dca": float(b["wealth"][0]), "paid": float(a["paid"][0]),
            "interest": float(a["interest"][0]), "calls": int(a["margin_calls"][0])}


def frontier_rules(es: ExposureStrategy) -> list:
    """Rules that size the borrowing against the account, as compared in the report (research/dca/round4-6)."""
    from perfectshape.dca.rules import Rule, flat, ladder, only_if, rate_guard, switch, trend, unless, vol_target

    g = rate_guard()
    x2 = [(-0.10, 0.20), (-0.20, 0.40), (-0.30, 0.60)]
    return [
        es.rule(),
        Rule("Crash 10% -> borrow 10% of the account (payments repay)", ladder([(-0.10, 0.10)]), False, "crash"),
        Rule("Crash 10 / 20 / 30% -> borrow 10 / 20 / 30%", ladder([(-0.10, 0.10), (-0.20, 0.20), (-0.30, 0.30)]), True, "crash"),
        Rule("Crash 10 / 20 / 30% -> borrow 20 / 40 / 60%", ladder(x2), True, "crash"),
        Rule("Crash ladder 20 / 40 / 60%, only once back above the 200-day average", ladder(x2, confirm=200), True, "crash"),
        Rule("Crash 30% -> borrow 100%", ladder([(-0.30, 1.0)]), True, "crash"),
        Rule("VIX above 30 -> borrow 25% (until below 20)", switch("vix", 30, 20, 1.25), True, "fear"),
        Rule("VIX above 40 -> borrow 50% (until below 20)", switch("vix", 40, 20, 1.5), True, "fear"),
        Rule("Volatility 2x usual -> borrow 50%", switch("rv_ratio", 2.0, 1.0, 1.5), True, "fear"),
        Rule("Policy news 2x usual -> borrow 50%", switch("epu", 2.0, 1.2, 1.5), True, "fear"),
        Rule("Calm market (volatility under 0.8x usual) -> borrow 50%", switch("rv_ratio", 0.8, 1.2, 1.5), True, "calm"),
        Rule("Volatility target 15%, exposure 1.0 to 1.5", vol_target(15, 1.0, 1.5), True, "calm"),
        Rule("Yields falling (6 months, -0.5 points) -> borrow 50%", switch("y10_chg", -0.5, 0.0, 1.5), True, "rates"),
        Rule("Always borrowed 25%", flat(1.25), True, "always"),
        Rule("Always borrowed 50%", flat(1.5), True, "always"),
        Rule("Trend 1.25 / 1.0 + rate guard (borrow only)", unless(trend(1.25), g), True, "trend"),
        Rule("Trend 1.25 / 0.75", trend(1.25, 0.75), True, "trend"),
        Rule("Trend 1.5 / 0.5, no guard", trend(1.5, 0.5), True, "trend"),
        Rule("Trend 2.0 / 0.5 + rate guard", unless(trend(2.0, 0.5), g), True, "trend"),
        Rule("Trend 2.0 / 1.0 + rate guard (borrow only)", unless(trend(2.0), g), True, "trend"),
        Rule("Trend 1.0 / 0.5 (cash only, no borrowing)", trend(1.0, 0.5), True, "trend"),
        Rule("Volatility-capped borrowing above the average", only_if(vol_target(15, 1.0, 1.5), lambda q: q["trend"] > 0), True, "trend"),
    ]


FKEYS = ("rule", "family", "n", "win", "median", "p10", "worst", "best", "dd_median", "dd_worst", "dd_vs_dca", "dd_vs_dca_worst",
         "dd_shallower", "dca_dd_median", "dca_dd_worst", "calls", "wiped", "avg_exposure", "turnover")


def exposure_section(us, es: ExposureStrategy, payment: float, quick: bool, own: bool) -> dict:
    """The account-sized borrowing rules: edge over plain DCA against how deep each fell."""
    from perfectshape.dca.exposure import ExposureConfig, simulate_exposure
    from perfectshape.dca.frontier import score

    cfg = ExposureConfig(payment=payment)
    f = features(us)
    rules = frontier_rules(es)
    step = 12 if quick else 3

    def slim(rows):
        return [{k: r[k] for k in FKEYS} for r in rows]

    out = {"strategy": asdict(es), "name": rules[0].name, "now": exposure_decision(us, f, es),
           "frontier": slim(score(us, rules, 10, cfg, step=step, feats=f)), "early": [], "checks": []}
    one = rules[:1]
    checks = [("5-year accounts", us, 5, cfg), ("10-year accounts", us, 10, cfg), ("20-year accounts", us, 20, cfg)]
    if not quick:
        checks += [("10-year, 0.2% cost per trade", us, 10, replace(cfg, trade_cost=0.002)),
                   ("10-year, margin rate 2 points above the 10-year yield", us, 10, replace(cfg, borrow_spread=0.02))]
    if not own:
        try:
            early = load_early_history()
            out["early"] = slim(score(early, rules, 10, cfg, step=step))
            checks.append(("10-year, S&P 1928-1961 (held out)", early, 10, cfg))
            if not quick:
                for tk, label in OTHER:
                    checks.append((f"10-year, {label}", load_other_market(tk), 10, cfg))
        except Exception as e:
            log.warning("dca report: exposure checks incomplete (%s)", e)
    for label, m, y, c in checks:
        rows = score(m, one, y, c, step=step)
        if rows:
            out["checks"].append({"label": label, **{k: rows[0][k] for k in FKEYS}})
    # one saver: time-weighted value against plain DCA's (drawdown chart)
    dates = us.index.values.astype("datetime64[D]")
    want = np.datetime64("1996-01-01") if dates[0] < np.datetime64("1996-01-01") else dates[0]
    i0 = int(np.flatnonzero(pay_days(dates) & (dates >= want))[0])
    args = (us["tr"].to_numpy(), dates)
    rates = (us["y10"].to_numpy(), us["y3m"].to_numpy())
    a = simulate_exposure(*args, rules[0].array(f), *rates, cfg, True, np.array([i0]), path=True)
    b = simulate_exposure(*args, np.ones(len(dates)), *rates, cfg, False, np.array([i0]), path=True)

    def dd(u):
        return u / np.maximum.accumulate(u) - 1.0

    sl = slice(i0, None, 5)
    out["path"] = {"start": str(dates[i0]), "dates": [str(d) for d in dates[sl]],
                   "dd": np.round(dd(a["unit_path"][i0:])[::5], 4).tolist(), "dd_dca": np.round(dd(b["unit_path"][i0:])[::5], 4).tolist(),
                   "exposure": np.round(a["exposure_path"][sl], 3).tolist(),
                   "final": float(a["wealth"][0]), "final_dca": float(b["wealth"][0]), "paid": float(a["paid"][0]),
                   "max_dd": float(a["max_dd"][0]), "max_dd_dca": float(b["max_dd"][0])}
    return out


def build_payload(s: Strategy = RECOMMENDED, payment: float = 2000.0, with_other: bool = True, quick: bool = False,
                  market=None, es: ExposureStrategy = EXPOSURE_RECOMMENDED) -> dict:
    """Everything the report shows. ``market``: a study frame to use instead of the downloaded S&P 500 history
    (then 1928-1961 and the other markets are left out)."""
    own = market is not None
    us = market if own else load_market()
    cfg = s.account(payment=payment)
    name = "Strategy: trend + rate guard"
    alts = alternatives(s)
    strat = {name: s.policy()}
    trio = {name: s.policy(), "Borrow above the 200-day average (monthly)": alts["Borrow above the 200-day average (monthly)"],
            "Always 6 payments ahead": const(-6)}
    p = {"name": "DCA timing", "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "payment": payment,
         "strategy": asdict(s), "account": asdict(cfg),
         "period": {"start": str(us.index[0].date()), "end": str(us.index[-1].date())}}
    f = features(us)
    p["now"] = decision(us, f, s)
    # 1. the alternatives, 10-year accounts, all start months
    p["alternatives"], p["edges10"] = _cmp(us, alts, 10, cfg, keep_edges=(name, "Always 6 payments ahead"))
    # 2. horizons and eras for the strategy and its two nearest alternatives
    p["horizons"] = {}
    for y in ((5, 10, 20) if quick else (5, 10, 20, 30)):
        rows, _ = _cmp(us, trio, y, cfg)
        if rows:
            p["horizons"][str(y)] = rows
    p["eras"] = {}
    for era, a, b in ERAS:
        rows, _ = _cmp(us, trio, 10, cfg, a, b)
        if rows:
            p["eras"][era] = rows
    try:
        if own:
            raise LookupError("a market was passed in")
        early = load_early_history()
        p["early"] = {str(y): _cmp(early, trio, y, cfg)[0] for y in (5, 10, 20)}
        _, p["edges10_early"] = _cmp(early, strat, 10, cfg, keep_edges=(name,))
        p["mechanism"] = mechanism([early, us], s)
    except Exception as e:                                         # no network on a first run: the report still stands
        if not own:
            log.warning("dca report: 1928-1961 not available (%s)", e)
        p["early"], p["edges10_early"], p["mechanism"] = {}, {}, mechanism([us], s)
    # 3. one change at a time
    sens = []
    if not quick:
        variants = [("as recommended", s, cfg)]
        variants += [(f"{n}-day average", replace(s, ma=n), cfg) for n in (150, 250, 300) if n != s.ma]
        variants += [("decide every day, not monthly", replace(s, monthly=False), cfg),
                     ("no rate guard", replace(s, guard_days=0), cfg),
                     ("rate guard at +0.4 points", replace(s, guard_rise=0.4), cfg),
                     ("rate guard at +0.8 points", replace(s, guard_rise=0.8), cfg),
                     ("3 payments ahead, not 6", replace(s, months=3.0), cfg),
                     ("debt up to 50% of the account (Reg T)", s, replace(cfg, initial_margin=0.5)),
                     ("debt up to 10% of the account", s, replace(cfg, initial_margin=0.9)),
                     ("margin rate 1 point above the 10-year yield", s, replace(cfg, borrow_spread=0.01)),
                     ("margin rate 2 points above", s, replace(cfg, borrow_spread=0.02)),
                     ("margin rate 3 points above", s, replace(cfg, borrow_spread=0.03)),
                     ("0.1% cost on every purchase", s, replace(cfg, trade_cost=0.001))]
        for label, sv, cv in variants:
            r10, _ = _cmp(us, {"x": sv.policy()}, 10, cv)
            r5, _ = _cmp(us, {"x": sv.policy()}, 5, cv)
            sens.append({"variant": label, "y10": r10["x"], "y5": r5["x"]})
    p["sensitivity"] = sens
    # 4. other markets (US rates; a check that the rule is not a law of nature)
    p["other"] = []
    if with_other and not quick and not own:
        for tk, label in OTHER:
            try:
                o = load_other_market(tk)
                rows, _ = _cmp(o, trio, 10, cfg)
                p["other"].append({"market": label, "start": str(o.index[0].date()), "rows": rows})
            except Exception as e:
                log.warning("dca report: %s not available (%s)", tk, e)
    # 5. savers
    first = us.index[0] + (us.index[-1] - us.index[0]) * 0.02
    starts = [d for d in ("1990-01-01", "2000-01-01", "2007-10-01", "2016-01-01") if str(us.index[0].date()) <= d < str(us.index[-1].date())]
    p["savers"] = [saver_path(us, s, d, cfg) for d in (starts or [str(first.date())])]
    p["exposure"] = exposure_section(us, es, payment, quick, own)
    return p


def _pct(x, d=1):
    return f"{x * 100:+.{d}f}%"


def summary_md(p: dict) -> str:
    name = "Strategy: trend + rate guard"
    n = p["now"]
    L = [f"# Beating monthly DCA into the S&P 500 ({p['period']['start']} to {p['period']['end']})", "",
         f"## This month ({n['date']})", "",
         f"**{n['text']}**", "",
         f"S&P 500 {n['px']:,.0f}, {_pct(n['vs_avg'])} against its {p['strategy']['ma']}-day average ({n['avg']:,.0f}), "
         f"{n['days_in_state']} trading days {'above' if n['above'] else 'below'}. 10-year yield {n['y10']:.2f}% "
         f"({n['y10_rise']:+.2f} points over {p['strategy']['guard_days']} trading days; the guard trips above "
         f"+{p['strategy']['guard_rise']}).", "",
         "## Against plain DCA, every start month", "",
         f"Edge = final wealth over plain DCA's - 1, for a saver paying ${p['payment']:,.0f} a month.", "",
         "| account length | start months | beats DCA | median edge | worst | best | median extra | margin calls |",
         "|---|---|---|---|---|---|---|---|"]
    for y, rows in p["horizons"].items():
        r = rows[name]
        L.append(f"| {y} years | {r['n']} | {r['win']:.0%} | {_pct(r['median'], 2)} | {_pct(r['worst'], 2)} | {_pct(r['best'], 2)} | "
                 f"${r['usd_median']:,.0f} | {r['calls']} |")
    if p["early"]:
        L += ["", "S&P 1928-1961 (not used to build the strategy):", "",
              "| account length | start months | beats DCA | median edge | worst | best |", "|---|---|---|---|---|---|"]
        for y, rows in p["early"].items():
            r = rows[name]
            L.append(f"| {y} years | {r['n']} | {r['win']:.0%} | {_pct(r['median'], 2)} | {_pct(r['worst'], 2)} | {_pct(r['best'], 2)} |")
    L += ["", "## What was tried (10-year accounts, 1962 to today)", "",
          "| policy | beats DCA | median edge | worst | best |", "|---|---|---|---|---|"]
    for k, r in p["alternatives"].items():
        L.append(f"| {k} | {r['win']:.0%} | {_pct(r['median'], 2)} | {_pct(r['worst'], 2)} | {_pct(r['best'], 2)} |")
    if p["mechanism"]:
        L += ["", "## Why: the S&P 500's return over the 10-year yield, by where the month starts", "",
              "| era | above the average | below the average |", "|---|---|---|"]
        for r in p["mechanism"]:
            L.append(f"| {r['era']} | {_pct(r['above_mean'])} a year (t {r['above_t']:.1f}, vol {r['above_vol']:.0%}, {r['above_months']} months) | "
                     f"{_pct(r['below_mean'])} a year (t {r['below_t']:.1f}, vol {r['below_vol']:.0%}, {r['below_months']} months) |")
    if p["sensitivity"]:
        L += ["", "## One change at a time", "", "| change | 10 years: beats DCA, median, worst | 5 years: beats DCA, median, worst |", "|---|---|---|"]
        for r in p["sensitivity"]:
            a, b = r["y10"], r["y5"]
            L.append(f"| {r['variant']} | {a['win']:.0%}, {_pct(a['median'], 2)}, {_pct(a['worst'], 2)} | "
                     f"{b['win']:.0%}, {_pct(b['median'], 2)}, {_pct(b['worst'], 2)} |")
    if p["other"]:
        L += ["", "## Other markets (10-year accounts, US rates)", "", "| market | strategy | trend only | always 6 ahead |", "|---|---|---|---|"]
        for o in p["other"]:
            c = lambda r: f"{r['win']:.0%}, {_pct(r['median'], 2)}, worst {_pct(r['worst'], 2)}"
            L.append(f"| {o['market']}, from {o['start'][:4]} | {c(o['rows'][name])} | "
                     f"{c(o['rows']['Borrow above the 200-day average (monthly)'])} | {c(o['rows']['Always 6 payments ahead'])} |")
    x = p.get("exposure")
    if x:
        def row(r):
            return (f"{r['win']:.0%} | {_pct(r['median'])} | {_pct(r['worst'])} | {_pct(r['dd_vs_dca'])} | "
                    f"{_pct(r['dd_vs_dca_worst'])} | {r['dd_shallower']:.0%} | {r['avg_exposure']:.2f}")

        L += ["", "## Borrowing sized against the account (rules that may also sell)", "",
              f"Exposure = position / equity (1 = plain DCA). **Today: {x['now']['text']}**", "",
              "Fall = the account's deepest drop, in points against plain DCA's over the same years (+ = shallower).", "",
              "| rule (10-year accounts, 1962 to today) | beats DCA | median edge | worst | fall vs DCA, median | worst | shallower in | average exposure |",
              "|---|---|---|---|---|---|---|---|"]
        for r in sorted(x["frontier"], key=lambda r: -r["median"]):
            L.append(f"| {'**' + r['rule'] + '**' if r['rule'] == x['name'] else r['rule']} | {row(r)} |")
        if x["checks"]:
            L += ["", f"### {x['name']}: checks", "",
                  "| | accounts | beats DCA | median edge | worst | fall vs DCA, median | worst | shallower in | average exposure |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for r in x["checks"]:
                L.append(f"| {r['label']} | {r['n']} | {row(r)} |")
    return "\n".join(L) + "\n"


def render_html(p: dict) -> str:
    page = (WEB / "dca.html").read_text(encoding="utf-8")
    data = json.dumps(p, default=float).replace("</", "<\\/")
    return (page.replace("/*__SHAPES_CSS__*/", (WEB / "shapes.css").read_text(encoding="utf-8"))
                .replace("__GENERATED__", html.escape(p["generated"])).replace("__DATA__", data))


def write_report(p: dict, root: str | Path = "runs", pages: list | None = None, run_dir: str | Path | None = None) -> Path:
    """Write the report (and, with ``pages`` from :func:`perfectshape.dca.pages.build_pages`, one page per rule under
    ``rules/``, linked from the report's tables)."""
    run_dir = Path(run_dir) if run_dir else Path(root) / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_dca"
    run_dir.mkdir(parents=True, exist_ok=True)
    if pages:
        from perfectshape.dca.pages import write_pages

        p["pages"] = write_pages(pages, run_dir)
    slim = {k: v for k, v in p.items() if k not in ("edges10", "edges10_early", "savers")}
    if "exposure" in slim:
        slim["exposure"] = {k: v for k, v in slim["exposure"].items() if k != "path"}
    slim.pop("pages", None)
    (run_dir / "dca.json").write_text(json.dumps(slim, indent=1, default=float), encoding="utf-8")
    (run_dir / "summary.md").write_text(summary_md(p), encoding="utf-8")
    (run_dir / "report.html").write_text(render_html(p), encoding="utf-8")
    return run_dir
