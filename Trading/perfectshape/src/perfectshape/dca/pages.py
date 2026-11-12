"""One page per rule of the DCA report: what the rule does, why anyone would expect it to work, what it held over
98 years, how it did against plain DCA by start month, horizon, era, cost and margin rate, and in every big crash.

``build_pages()`` computes everything (on a process pool: about 45 independent simulations); ``write_pages()``
writes ``rules/<slug>.html`` next to the report. Two kinds of rule:

* ``exposure`` (``report.frontier_rules``): the account's exposure (position / equity) follows a signal; most sell.
  These also run as one account over 1928-2026 (the 1928-1961 S&P history chained to the 1962-2026 one), which
  gives the time-weighted growth, drawdowns, decades and crashes on the page.
* ``payments`` (``report.alternatives``): up to six payments held back or borrowed ahead, never sells.
"""

from __future__ import annotations

import html
import json
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parents[1] / "web"

# ---------------------------------------------------------------- what each rule is, in words

_TREND_IDEA = ("Since 1928, months that began with the S&P 500 above its 200-day average beat the 10-year Treasury "
               "yield by about 9.5% a year at 14% volatility; months that began below it beat the yield by about 1% at "
               "25%. Borrowing pays only when stocks beat the loan's rate, so the rule borrows where that premium has "
               "been reliable and stops where it has not.")
_TREND_RISK = ("Whipsaw: every time the index crosses its average the rule sells (just after a fall) or buys back (just "
               "after a rise), so choppy sideways years cost it money. A crash that begins while the index is above its "
               "average is taken at the higher exposure until the crossing. It trades often, so costs and taxes on the "
               "sales matter; it is an S&P 500 finding (weaker on other indices).")
_GUARD = (" The rate guard caps exposure at 1.0 (no new debt) while the 10-year yield has risen more than 0.6 points over "
          "the last 126 trading days: sharp rate rises came before the worst stretches for borrowed money (1969, 1973, "
          "1981, 1987, 1994, 2022).")
_CRASH_IDEA = ("Buy the dip: every S&P 500 fall since 1928 was eventually recovered, so money invested after a fall bought "
               "cheaper shares that later rose. Borrowing more the deeper it falls is the classic 'be greedy when others "
               "are fearful'.")
_CRASH_RISK = ("A 10% fall is usually not the bottom: 1973-74, 2000-02 and 2007-09 fell another 39 to 51% after a 10% "
               "trigger, with the debt on all the way down, and the recovery to within 2% of the old high took five to "
               "seven years of interest. Keeping a constant exposure while prices fall also means selling shares on the way "
               "down. Whether it wins depends on when in a saver's life the big crash arrives.")
_FEAR_RISK = ("Fear signals arrive in the middle of a fall, not at its end: in 2008 the VIX passed 30 in September, two "
              "months and another 30% before the bottom. The signal often flips on and off around its threshold.")

DOCS: dict[str, dict[str, str]] = {
    # ---- account-sized rules
    "Trend 1.5 / 0.5 + rate guard": {
        "what": "Borrow half the account (1.5x) while the S&P 500 is above its 200-day average; keep half the account in "
                "T-bills (0.5x) while it is below. The recommended account-sized rule.",
        "how": "Every day, from the previous close: exposure 1.5 if the index is above its 200-day average, 0.5 if below." + _GUARD
               + " The account sells or buys whenever it is more than 2% of equity off its target; payments are invested up "
                 "to the target.",
        "idea": _TREND_IDEA + " The borrowing above the average earns more than the cash below it costs, and the cash is what "
                              "makes the account fall less than plain DCA in a long bear market.",
        "risk": _TREND_RISK,
    },
    "Trend 1.25 / 1.0 + rate guard (borrow only)": {
        "what": "Borrow a quarter of the account (1.25x) while the S&P 500 is above its 200-day average; plain DCA (1.0x, "
                "no debt, no cash) below it.",
        "how": "Every day, from the previous close: exposure 1.25 above the 200-day average, 1.0 below." + _GUARD
               + " Sells to repay when the index crosses below the average.",
        "idea": _TREND_IDEA + " It only adds; it never holds cash, so it cannot fall less than plain DCA, only a little more.",
        "risk": _TREND_RISK,
    },
    "Trend 1.25 / 0.75": {
        "what": "Borrow a quarter of the account above the 200-day average; keep a quarter of it in T-bills below.",
        "how": "Every day, from the previous close: exposure 1.25 above the 200-day average, 0.75 below. No rate guard.",
        "idea": _TREND_IDEA + " The mildest rule that both borrows and steps aside: the most consistent, the smallest edge.",
        "risk": _TREND_RISK,
    },
    "Trend 1.5 / 0.5, no guard": {
        "what": "The recommended rule without its rate guard: 1.5x above the 200-day average, 0.5x below, whatever rates do.",
        "how": "Every day, from the previous close: exposure 1.5 above the 200-day average, 0.5 below.",
        "idea": _TREND_IDEA + " Shown to measure what the rate guard adds.",
        "risk": _TREND_RISK + " Without the guard it also borrows into rate shocks such as 1973 and 2022.",
    },
    "Trend 2.0 / 0.5 + rate guard": {
        "what": "Double the account (borrow 100% of equity) above the 200-day average; half the account in T-bills below.",
        "how": "Every day, from the previous close: exposure 2.0 above the 200-day average, 0.5 below." + _GUARD
               + " 2.0 is the Reg T limit for a margin account.",
        "idea": _TREND_IDEA + " The most aggressive version that still steps aside: about twice the edge of 1.5 / 0.5.",
        "risk": _TREND_RISK + " At 2.0 the account sits at the margin limit: a single day of about -29% would force a sale, and "
                              "the part of a crash before the crossing is taken at double exposure.",
    },
    "Trend 2.0 / 1.0 + rate guard (borrow only)": {
        "what": "Double the account (borrow 100% of equity) above the 200-day average; plain DCA (fully invested, no debt, "
                "no cash) below it.",
        "how": "Every day, from the previous close: exposure 2.0 above the 200-day average, 1.0 below." + _GUARD
               + " When the index crosses below its average the account sells half its shares to repay the loan; it "
                 "rebalances whenever it drifts more than 2% of equity off target, which at 2.0 is after almost every 1% move.",
        "idea": _TREND_IDEA + " This rule takes the premium at full size: on average it is about 1.6x exposed.",
        "risk": "It never holds cash, so it cannot fall less than plain DCA: the part of every crash before the index crosses "
                "its average is taken at double exposure. " + _TREND_RISK + " Borrowing 100% of equity at the 10-year "
                "Treasury yield is cheaper than any broker charges.",
    },
    "Trend 1.0 / 0.5 (cash only, no borrowing)": {
        "what": "Never borrow: fully invested above the 200-day average, half the account in T-bills below it.",
        "how": "Every day, from the previous close: exposure 1.0 above the 200-day average, 0.5 below.",
        "idea": "The classic trend-following defence: step half out of a falling market. Shown to separate what the cash does "
                "(cuts the fall) from what the borrowing does (adds the edge).",
        "risk": "Stocks beat T-bills on average even below the average, so the cash costs return: it loses to plain DCA in about "
                "half the accounts. Whipsaw sells low and buys back higher.",
    },
    "Volatility-capped borrowing above the average": {
        "what": "Borrow only above the 200-day average, and only as much as calm markets allow: exposure = 15% / recent "
                "volatility, between 1.0 and 1.5.",
        "how": "On payday the volatility target is set: 15 divided by the S&P 500's realised volatility over the last 21 days "
               "(in % a year), clipped to 1.0-1.5. It applies only while the index is above its 200-day average; below it, 1.0.",
        "idea": "Borrow more when the market is calm (calm stretches tend to continue and to rise) and less when it is choppy, "
                "but never against the trend.",
        "risk": "Volatility is lowest at market tops; the cap does not step aside in a fall.",
    },
    "Volatility target 15%, exposure 1.0 to 1.5": {
        "what": "Hold more of the market the calmer it is: exposure = 15% / recent volatility, between 1.0 and 1.5.",
        "how": "On payday: 15 divided by the S&P 500's realised volatility over the last 21 trading days (% a year), clipped to "
               "1.0-1.5, held for the month.",
        "idea": "Volatility clusters: calm months tend to follow calm months, and risk-adjusted returns have been higher in calm "
                "markets. Volatility targeting is a standard fund overlay.",
        "risk": "The calmest markets come just before the shocks (1987, 2007, 2018, 2020): the rule is at full leverage when "
                "volatility jumps, and only cuts after the first leg down.",
    },
    "Crash 10% -> borrow 10% of the account (payments repay)": {
        "what": "When the S&P 500 is 10% or more below its all-time high, borrow 10% of the account and invest it. Never sells: "
                "the monthly payments repay the debt once the market has recovered.",
        "how": "Exposure 1.1 from the day the index closes 10% below its high until it is back within 2% of that high. After "
               "that the target is 1.0, but the account does not sell: payments go to the debt first.",
        "idea": _CRASH_IDEA,
        "risk": _CRASH_RISK,
    },
    "Crash 10 / 20 / 30% -> borrow 10 / 20 / 30%": {
        "what": "A ladder: borrow 10% of the account when the S&P 500 is 10% below its high, 20% at -20%, 30% at -30%.",
        "how": "The deepest step reached is kept until the index is back within 2% of its all-time high; then the account "
               "sells to repay. While the steps are on, it keeps the exposure constant, selling a little as prices fall.",
        "idea": _CRASH_IDEA,
        "risk": _CRASH_RISK,
    },
    "Crash 10 / 20 / 30% -> borrow 20 / 40 / 60%": {
        "what": "The double ladder: borrow 20% of the account at -10%, 40% at -20%, 60% at -30%.",
        "how": "The deepest step reached is kept until the index is back within 2% of its all-time high, then sold down. "
               "While on, the exposure is kept constant (1.2, 1.4 or 1.6), selling as prices fall.",
        "idea": _CRASH_IDEA,
        "risk": _CRASH_RISK,
    },
    "Crash ladder 20 / 40 / 60%, only once back above the 200-day average": {
        "what": "The double ladder, but a step is only taken on a day the S&P 500 is back above its 200-day average: buy the "
                "recovery, not the fall.",
        "how": "Steps of 20 / 40 / 60% at drawdowns of 10 / 20 / 30% from the high, taken only while the index is above its "
               "200-day average; once taken, held until the index is within 2% of its high.",
        "idea": _CRASH_IDEA + " Waiting for the trend to turn avoids borrowing on the way down.",
        "risk": "By the time the index is back above its average, much of the rebound is gone; and a second leg down after "
                "a bear-market rally (2001, 2008) catches it borrowed.",
    },
    "Crash 30% -> borrow 100%": {
        "what": "All in: double the account (borrow 100% of equity) once the S&P 500 is 30% below its high.",
        "how": "Exposure 2.0 from the day the index is 30% below its all-time high until it is back within 2% of it. "
               "It sells to keep 2.0 as prices fall.",
        "idea": _CRASH_IDEA + " Falls of 30% are rare (about a dozen since 1928), so this borrows only in real bear markets.",
        "risk": "1929-32 fell 86% and 2007-09 57%: at 2.0 the account loses twice the further fall and sells all the way down. "
                + _CRASH_RISK,
    },
    "VIX above 30 -> borrow 25% (until below 20)": {
        "what": "Borrow a quarter of the account when the VIX (the market's 'fear gauge') closes above 30, until it is back "
                "below 20.",
        "how": "Exposure 1.25 from the day the VIX closes at 30 or more until it closes at 20 or less. No VIX before 1990: "
               "the rule holds 1.0 then.",
        "idea": "A high VIX means expensive options and forced selling; returns after VIX spikes have been above average.",
        "risk": _FEAR_RISK,
    },
    "VIX above 40 -> borrow 50% (until below 20)": {
        "what": "Borrow half the account in real panics: VIX above 40, until it is back below 20.",
        "how": "Exposure 1.5 from the day the VIX closes at 40 or more until it closes at 20 or less (1998, 2002, 2008-09, "
               "2011, 2020). No VIX before 1990.",
        "idea": "The panics that pushed the VIX above 40 were all good buying points with hindsight.",
        "risk": _FEAR_RISK + " So rare that most accounts never trigger it.",
    },
    "Volatility 2x usual -> borrow 50%": {
        "what": "Borrow half the account when the S&P 500's recent volatility is twice its usual level.",
        "how": "Exposure 1.5 from the day the 21-day realised volatility reaches 2x its median of the past year, until it is "
               "back to 1x. Uses prices only, so it covers 1928-2026.",
        "idea": "Volatility spikes mark forced selling; returns after them have been above average (the VIX idea, from prices).",
        "risk": _FEAR_RISK,
    },
    "Policy news 2x usual -> borrow 50%": {
        "what": "Borrow half the account when newspapers are full of economic-policy uncertainty: the news index at twice its "
                "usual level.",
        "how": "The daily US Economic Policy Uncertainty index (Baker, Bloom and Davis: articles in US newspapers about "
               "economic policy and uncertainty). Exposure 1.5 when its 21-day average reaches 2x its median of the past two "
               "years, until it is back to 1.2x. Data from 1985.",
        "idea": "Uncertainty spikes (elections, debt ceilings, tariffs, pandemics) scare investors out; prices tend to recover "
                "once the news calms.",
        "risk": "Some policy shocks are real (2008, 2020 lockdowns) and the market keeps falling; the signal is noisy.",
    },
    "Calm market (volatility under 0.8x usual) -> borrow 50%": {
        "what": "The opposite of the fear rules: borrow half the account when the market is unusually calm.",
        "how": "Exposure 1.5 from the day the 21-day realised volatility falls to 0.8x its median of the past year, until it "
               "rises to 1.2x.",
        "idea": "Calm markets tend to keep rising ('the market climbs a wall of worry'); low-volatility regimes persist.",
        "risk": "Calm ends abruptly (Feb 2018, Feb 2020): the rule is borrowed on the first day of the shock and only steps "
                "back once volatility is already high.",
    },
    "Yields falling (6 months, -0.5 points) -> borrow 50%": {
        "what": "Borrow half the account when the 10-year Treasury yield has fallen by half a point or more in six months.",
        "how": "Exposure 1.5 from the day the 10-year yield is 0.5 points below its level 126 trading days ago, until the "
               "six-month change is back to zero or above.",
        "idea": "Falling yields make borrowing cheaper and future cash flows worth more; the rate signal was the most "
                "consistent single predictor in the forecasting study.",
        "risk": "Yields also fall in a flight to safety at the start of recessions (2001, 2008): the rule borrows into them.",
    },
    "Always borrowed 25%": {
        "what": "Permanent leverage: always 1.25x, rebalanced.",
        "how": "Exposure 1.25 every day: the account buys after rises and sells after falls to stay at 1.25.",
        "idea": "Stocks beat the 10-year yield on average, so any borrowing pays on average. The benchmark for every "
                "timing rule: does the timing add anything beyond the average leverage?",
        "risk": "No timing: it carries the debt through every bear market and rebalances by selling into falls.",
    },
    "Always borrowed 50%": {
        "what": "Permanent leverage: always 1.5x, rebalanced.",
        "how": "Exposure 1.5 every day: buy after rises, sell after falls.",
        "idea": "As for 1.25x, at twice the size.",
        "risk": "A 50% fall takes 75% of the account; the rebalancing sells at the bottom.",
    },
    # ---- six-payment rules
    "Strategy: trend + rate guard": {
        "what": "The recommended six-payment rule: on payday, if the S&P 500 is above its 200-day average and rates are not "
                "jumping, borrow until you are six payments ahead; otherwise borrow nothing new.",
        "how": "On payday, from the previous close: target -6 payments (six of debt) if the index is above its 200-day average "
               "and the 10-year yield has not risen more than 0.6 points in 126 trading days; otherwise 0. Debt never above "
               "25% of the account. Never sells: payments repay the debt first.",
        "idea": _TREND_IDEA,
        "risk": "Six payments are a sliver of a grown account, so the edge is a few percent. A crash that starts above the "
                "average hits before the rule stops borrowing; young accounts feel it most.",
    },
    "Borrow above the 200-day average (monthly)": {
        "what": "The same trend rule without the rate guard: six payments ahead whenever the S&P 500 is above its 200-day "
                "average on payday.",
        "how": "On payday, from the previous close: target -6 payments above the 200-day average, 0 below, held for the month. "
               "Debt never above 25% of the account; never sells.",
        "idea": _TREND_IDEA,
        "risk": "Borrows into rate shocks (1973, 1987, 2022), which is what the rate guard removes.",
    },
    "Borrow below the 200-day average": {
        "what": "The contrarian version: six payments ahead while the S&P 500 is below its 200-day average.",
        "how": "Any day, from the previous close: target -6 payments below the 200-day average, 0 above.",
        "idea": "Buy what is down: below-average markets are cheaper.",
        "risk": "Below-average months returned barely more than the loan rate since 1928, at nearly twice the volatility.",
    },
    "Borrow on fear (vol spike / high VIX)": {
        "what": "Six payments ahead while the market is frightened: volatility spiking or the VIX unusually high.",
        "how": "Any day, from the previous close: target -6 payments while the 21-day volatility is above 1.3x its yearly median "
               "or the VIX is in the top fifth of its last five years; 0 otherwise.",
        "idea": "Fear marks forced selling; returns after it have been above average.",
        "risk": _FEAR_RISK,
    },
    "Borrow after a 10% drawdown": {
        "what": "Six payments ahead while the S&P 500 is 10% or more below its high of the past year.",
        "how": "Any day, from the previous close: target -6 payments while the index is at least 10% under its 1-year high; "
               "0 otherwise.",
        "idea": _CRASH_IDEA,
        "risk": _CRASH_RISK,
    },
    "Invest 4 days before month end": {
        "what": "Borrow the coming payment four trading days before the month ends and repay it on payday: the turn-of-the-"
                "month effect.",
        "how": "Target -1 payment from the 4th-last trading day of each month until the payment arrives on the first trading day "
               "of the next; 0 otherwise.",
        "idea": "Stocks have earned a disproportionate share of their return around the turn of the month (salary and pension "
                "flows), in every era tested.",
        "risk": "Tiny by construction: one payment for a few days a month.",
    },
    "Always 6 payments ahead": {
        "what": "Permanently six payments of debt: every payment is invested six months early.",
        "how": "Target -6 payments every day; debt never above 25% of the account; never sells.",
        "idea": "Stocks beat the 10-year yield on average, so investing earlier pays on average.",
        "risk": "No timing: the debt is carried through every bear market. It lost in more than half of the 1962-1989 accounts.",
    },
    "Always 1 payment ahead": {
        "what": "Permanently one payment of debt: every payment invested a month early.",
        "how": "Target -1 payment every day.",
        "idea": "As for six payments ahead, at a sixth of the size.",
        "risk": "As for six payments ahead.",
    },
    "Wait for a 5% dip, else hold": {
        "what": "Hold payments in cash (up to six) until the S&P 500 is 5% below its 1-year high, then invest them all.",
        "how": "Target +6 payments (six in T-bills) while the index is within 5% of its 1-year high; 0 once it is 5% or more "
               "below. When six are held, each new payment is invested as it arrives.",
        "idea": "Buy the dips instead of the highs.",
        "risk": "Markets spend most of their time near their highs and rise from there: waiting costs more than the dips "
                "save.",
    },
    "Hold 6 payments in cash": {
        "what": "Always keep six payments in T-bills: every payment is invested six months late.",
        "how": "Target +6 payments every day.",
        "idea": "Dry powder for a crash.",
        "risk": "Without a rule to spend it, the cash only earns T-bills while stocks earn more.",
    },
    "Hold every payment 1 month": {
        "what": "Every payment waits a month in T-bills.",
        "how": "Target +1 payment every day.",
        "idea": "The mirror of 'always one ahead': a test of whether waiting pays.",
        "risk": "It does not, in any era tested.",
    },
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]


def page_href(name: str) -> str:
    return f"rules/{slug(name)}.html"


# ---------------------------------------------------------------- data shared by the workers

CRASHES = [("1929-32", "1929-06-01", "1932-12-31"), ("1937-38", "1937-01-01", "1938-12-31"), ("1946-49", "1946-01-01", "1949-12-31"),
           ("1962", "1961-11-01", "1962-12-31"), ("1966", "1965-12-01", "1966-12-31"), ("1968-70", "1968-10-01", "1970-12-31"),
           ("1973-74", "1972-12-01", "1974-12-31"), ("1980-82", "1980-10-01", "1982-12-31"), ("1987", "1987-07-01", "1987-12-31"),
           ("1990", "1990-06-01", "1990-12-31"), ("2000-02", "2000-01-01", "2002-12-31"), ("2007-09", "2007-07-01", "2009-06-30"),
           ("2020", "2020-01-01", "2020-06-30"), ("2022", "2021-12-01", "2022-12-31")]
X_SETTINGS = {"us5": ("5-year accounts, 1962 to today", "us", 5, {}), "us10": ("10-year accounts, 1962 to today", "us", 10, {}),
              "us20": ("20-year accounts, 1962 to today", "us", 20, {}),
              "early10": ("10-year accounts, S&P 1928-1961 (held out)", "early", 10, {}),
              "cost": ("10-year, 0.2% cost on every trade", "us", 10, {"trade_cost": 0.002}),
              "margin": ("10-year, margin rate 2 points above the 10-year yield", "us", 10, {"borrow_spread": 0.02})}
P_SETTINGS = {"us5": ("5-year accounts, 1962 to today", "us", 5), "us10": ("10-year accounts, 1962 to today", "us", 10),
              "us20": ("20-year accounts, 1962 to today", "us", 20), "us30": ("30-year accounts, 1962 to today", "us", 30),
              "early10": ("10-year accounts, S&P 1928-1961 (held out)", "early", 10),
              "early20": ("20-year accounts, S&P 1928-1961 (held out)", "early", 20)}
STEP = 3          # every third start month
DS = 5            # chart points: every fifth trading day


@lru_cache(maxsize=1)
def _markets():
    import pandas as pd

    from perfectshape.dca.data import load_early_history, load_market
    from perfectshape.dca.signals import features

    us, early = load_market(), load_early_history()
    e = early[early.index < us.index[0]]
    m = pd.concat([e, us])
    r = pd.concat([e["tr"].pct_change(), us["tr"].pct_change()])
    r.iloc[len(e)] = us["px"].iloc[0] / e["px"].iloc[-1] - 1.0          # the seam: price move only
    m["tr"] = (1.0 + r.fillna(0.0)).cumprod()
    m["y3m"] = m["y3m"].fillna(0.0)
    return {"us": us, "early": early, "all": m, "f_us": features(us), "f_early": features(early), "f_all": features(m)}


@lru_cache(maxsize=1)
def _rules():
    from perfectshape.dca.report import alternatives, frontier_rules
    from perfectshape.dca.strategy import EXPOSURE_RECOMMENDED, RECOMMENDED

    return frontier_rules(EXPOSURE_RECOMMENDED), alternatives(RECOMMENDED)


def _ds(a, nd=4):
    return np.round(np.asarray(a, dtype=float)[::DS], nd).tolist()


def _x_score(key):
    from perfectshape.dca.exposure import ExposureConfig
    from perfectshape.dca.frontier import score
    from perfectshape.dca.report import FKEYS

    label, mk, years, kw = X_SETTINGS[key]
    M = _markets()
    rules = _rules()[0]
    rows = score(M[mk], rules, years, ExposureConfig(**kw), step=STEP, feats=M[f"f_{mk}"])
    out = []
    for r in rows:
        d = {k: r[k] for k in FKEYS}
        if key in ("us10", "early10"):
            d["edges"] = np.round(r["edges"], 5).tolist()
            d["dates"] = [str(x) for x in r["start_dates"]]
        out.append(d)
    return ("x_score", key, out)


def _p_score(key):
    from perfectshape.dca.evaluate import compare
    from perfectshape.dca.policy import const, to_array
    from perfectshape.dca.strategy import RECOMMENDED

    label, mk, years = P_SETTINGS[key]
    M = _markets()
    f = M[f"f_{mk}"]
    pols = _rules()[1]
    targets = {"dca": to_array(const(0), f), **{k: to_array(p, f) for k, p in pols.items()}}
    out = compare(M[mk], targets, years, RECOMMENDED.account())
    res = {}
    for k, v in out.items():
        d = {c: v[c] for c in ("n", "win", "median", "mean", "p10", "worst", "best", "usd_median", "usd_worst", "interest", "calls")}
        if key in ("us10", "early10"):
            d["edges"] = np.round(v["edges"], 5).tolist()
            d["dates"] = [str(x) for x in v["start_dates"]]
        res[k] = d
    return ("p_score", key, res)


def _x_path(i):
    from perfectshape.dca.exposure import ExposureConfig

    return ("x_path", i, path_data(_rules()[0][i], ExposureConfig()))


def path_data(rule, cfg) -> dict:
    """One account following ``rule`` over 1928-today (time-weighted growth, falls, crashes, decades) with ``cfg``."""
    from perfectshape.dca.account import pay_days
    from perfectshape.dca.exposure import ExposureConfig, simulate_exposure

    M = _markets()
    m, f = M["all"], M["f_all"]
    dates = m.index.values.astype("datetime64[D]")
    i0 = int(np.flatnonzero(pay_days(dates))[0])
    target = rule.array(f)
    args = (m["tr"].to_numpy(), dates)
    rates = (m["y10"].to_numpy(), m["y3m"].to_numpy())
    a = simulate_exposure(*args, target, *rates, cfg, rule.sell, np.array([i0]), path=True)
    b = simulate_exposure(*args, np.ones(len(dates)), *rates, ExposureConfig(), False, np.array([i0]), path=True)
    ua, ub = a["unit_path"], b["unit_path"]
    dd = lambda u: u / np.maximum.accumulate(u) - 1.0
    px = m["px"]
    avg = px.rolling(200).mean()
    crashes = []
    for name, s, e in CRASHES:
        w = px[s:e]
        if len(w) < 20:
            continue
        pk = w.idxmax()
        tr_ = w[pk:].idxmin()
        ip, it = m.index.get_loc(pk), m.index.get_loc(tr_)
        ir = min(it + 252, len(m) - 1)
        if ua[ip] <= 0 or ua[it] <= 0:
            fall_a, rec_a = -1.0, 0.0
        else:
            fall_a, rec_a = ua[it] / ua[ip] - 1.0, ua[ir] / ua[it] - 1.0
        crashes.append({"name": name, "peak": str(pk.date()), "trough": str(tr_.date()), "index_fall": float(px[tr_] / px[pk] - 1.0),
                        "fall": float(fall_a), "fall_dca": float(ub[it] / ub[ip] - 1.0),
                        "avg_exposure": float(np.mean(a["exposure_path"][ip:it + 1])),
                        "exposure_at_peak": float(a["exposure_path"][ip]),
                        "year_after": float(rec_a), "year_after_dca": float(ub[ir] / ub[it] - 1.0)})
    years = m.index.year
    decades = []
    for d0 in range(1930, 2030, 10):
        mask = np.flatnonzero((years >= d0) & (years < d0 + 10))
        if len(mask) < 252:
            continue
        s, e = mask[0], mask[-1]
        yrs = len(mask) / 252.0
        g = lambda u: (u[e] / u[s]) ** (1 / yrs) - 1.0 if u[s] > 0 and u[e] > 0 else -1.0
        decades.append({"decade": f"{d0}s", "cagr": float(g(ua)), "cagr_dca": float(g(ub)),
                        "avg_exposure": float(np.mean(a["exposure_path"][s:e + 1])), "max_dd": float(dd(ua[s:e + 1] / ua[s]).min()) if ua[s] > 0 else -1.0,
                        "max_dd_dca": float(dd(ub[s:e + 1] / ub[s]).min())})
    sl = slice(i0, None)
    series = {"dates": [str(x) for x in dates[sl][::DS]], "px": _ds(px.to_numpy()[sl], 2), "avg": _ds(avg.to_numpy()[sl], 2),
              "target": _ds(target[sl], 3), "exposure": _ds(a["exposure_path"][sl], 3),
              "unit": _ds(ua[sl], 5), "unit_dca": _ds(ub[sl], 5), "dd": _ds(dd(np.maximum(ua[sl], 1e-12)), 4), "dd_dca": _ds(dd(ub[sl]), 4)}
    n_years = (len(dates) - i0) / 252.0
    whole = {"cagr": float(ua[-1] ** (1 / n_years) - 1.0) if ua[-1] > 0 else -1.0, "cagr_dca": float(ub[-1] ** (1 / n_years) - 1.0),
             "max_dd": float(a["max_dd"][0]), "max_dd_dca": float(b["max_dd"][0]), "calls": int(a["margin_calls"][0]),
             "wiped": bool(a["wiped"][0]), "avg_exposure": float(a["avg_exposure"][0]), "start": str(dates[i0]),
             "share_borrowed": float((a["exposure_path"][sl] > 1.001).mean()), "share_cash": float((a["exposure_path"][sl] < 0.999).mean()),
             "switches_per_year": float((np.abs(np.diff(target[sl])) > 1e-9).sum() / n_years)}
    return {"series": series, "crashes": crashes, "decades": decades, "whole": whole}


def _p_path(name):
    from perfectshape.dca.account import pay_days, simulate
    from perfectshape.dca.policy import to_array
    from perfectshape.dca.strategy import RECOMMENDED

    M = _markets()
    pol = _rules()[1][name]
    m, f = M["all"], M["f_all"]
    tg_all = to_array(pol, f)
    px = m["px"]
    avg = px.rolling(200).mean()
    us, fu = M["us"], M["f_us"]
    tg = to_array(pol, fu)
    dates = us.index.values.astype("datetime64[D]")
    i0 = int(np.flatnonzero(pay_days(dates) & (dates >= np.datetime64("2000-01-01")))[0])
    args = (us["tr"].to_numpy(), dates)
    rates = (us["y10"].to_numpy(), us["y3m"].to_numpy())
    cfg = RECOMMENDED.account()
    a = simulate(*args, tg, *rates, cfg, starts=np.array([i0]), path=True)
    b = simulate(*args, np.zeros(len(dates)), *rates, cfg, starts=np.array([i0]), path=True)
    sl = slice(i0, None, DS)
    alld = m.index.values.astype("datetime64[D]")
    j0 = 200
    return ("p_path", name, {
        "series": {"dates": [str(x) for x in alld[j0::DS]], "px": _ds(px.to_numpy()[j0:], 2), "avg": _ds(avg.to_numpy()[j0:], 2),
                   "target": _ds(tg_all[j0:], 2)},
        "saver": {"start": str(dates[i0]), "dates": [str(x) for x in dates[sl]], "extra": np.round(a["wealth_path"][sl] - b["wealth_path"][sl], 0).tolist(),
                  "cash": np.round(a["cash_path"][sl], 0).tolist(), "final": float(a["wealth"][0]), "final_dca": float(b["wealth"][0]),
                  "paid": float(a["paid"][0]), "interest": float(a["interest"][0]), "calls": int(a["margin_calls"][0])},
        "time": {"share_borrowed": float((tg_all[j0:] < 0).mean()), "share_holding": float((tg_all[j0:] > 0).mean()),
                 "mean_target": float(tg_all[j0:].mean())}})


def _task(job):
    import logging
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    kind, arg = job
    return {"x_score": _x_score, "p_score": _p_score, "x_path": _x_path, "p_path": _p_path}[kind](arg)


# ---------------------------------------------------------------- pages

def _verdict_x(st: dict) -> str:
    r, e = st["us10"], st.get("early10")
    pct = lambda x: f"{x * 100:+.1f}%"
    s = (f"Over {r['n']} ten-year accounts opened since 1962 it beat plain DCA in {r['win']:.0%} of them: median {pct(r['median'])}, "
         f"worst {pct(r['worst'])}, best {pct(r['best'])}. ")
    d = r["dd_vs_dca"]
    if d > 0.002:
        s += (f"Its deepest fall was shallower than plain DCA's by a median of {d * 100:.1f} points (shallower in "
              f"{r['dd_shallower']:.0%} of accounts; at worst {-r['dd_vs_dca_worst'] * 100:.1f} points deeper). ")
    elif d < -0.002:
        s += (f"Its deepest fall was deeper than plain DCA's by a median of {-d * 100:.1f} points (worst {-r['dd_vs_dca_worst'] * 100:.1f} "
              "points deeper). ")
    else:
        s += f"Its deepest fall was about the same as plain DCA's (worst {-r['dd_vs_dca_worst'] * 100:.1f} points deeper). "
    if e and e["n"]:
        if abs(e["avg_exposure"] - 1.0) < 1e-6:
            s += "Its signal has no data before 1962, so in 1928-1961 it simply was plain DCA."
        else:
            s += (f"In 1928-1961, which played no part in choosing any rule, it beat DCA in {e['win']:.0%} of {e['n']} accounts "
                  f"(median {pct(e['median'])}, worst {pct(e['worst'])}) and fell "
                  + (f"{e['dd_vs_dca'] * 100:.1f} points less" if e["dd_vs_dca"] > 0.002 else
                     f"{-e['dd_vs_dca'] * 100:.1f} points more" if e["dd_vs_dca"] < -0.002 else "about as far")
                  + " than plain DCA (median).")
    return s


def _verdict_p(st: dict) -> str:
    r, e = st["us10"], st.get("early10")
    pct = lambda x: f"{x * 100:+.2f}%"
    s = (f"Over {r['n']} ten-year accounts opened since 1962 it beat plain DCA in {r['win']:.0%} of them: median {pct(r['median'])} "
         f"(${r['usd_median']:,.0f} on a $240,000 ten-year saving), worst {pct(r['worst'])}, best {pct(r['best'])}. ")
    if e and e["n"]:
        s += f"In 1928-1961 (held out): {e['win']:.0%} of {e['n']} accounts, median {pct(e['median'])}, worst {pct(e['worst'])}."
    return s


def build_pages(workers: int = 0, generated: str | None = None) -> list[dict]:
    """Every page's data (a list of dicts, one per rule), computed on a process pool."""
    import os

    xrules, prules = _rules()
    jobs = ([("x_score", k) for k in X_SETTINGS] + [("p_score", k) for k in P_SETTINGS]
            + [("x_path", i) for i in range(len(xrules))] + [("p_path", k) for k in prules])
    n = workers or min(len(jobs), max(1, (os.cpu_count() or 2) - 2))
    if n == 1:
        results = [_task(j) for j in jobs]
    else:
        with ProcessPoolExecutor(n) as ex:
            results = list(ex.map(_task, jobs))
    xs = {k: v for kind, k, v in results if kind == "x_score"}
    ps = {k: v for kind, k, v in results if kind == "p_score"}
    xp = {k: v for kind, k, v in results if kind == "x_path"}
    pp = {k: v for kind, k, v in results if kind == "p_path"}
    generated = generated or datetime.now().strftime("%Y-%m-%d %H:%M")
    nav = ([{"name": r.name, "href": slug(r.name) + ".html", "kind": "exposure", "family": r.family} for r in xrules]
           + [{"name": k, "href": slug(k) + ".html", "kind": "payments", "family": "payments"} for k in prules])
    pages = []
    for i, r in enumerate(xrules):
        st = {k: {**xs[k][i], "label": X_SETTINGS[k][0]} for k in X_SETTINGS}
        edges = {k: {"dates": st[k].pop("dates"), "edge": st[k].pop("edges")} for k in ("us10", "early10")}
        for k in st:
            st[k].pop("dates", None)
            st[k].pop("edges", None)
        pages.append({"kind": "exposure", "name": r.name, "family": r.family, "sell": r.sell, "generated": generated,
                      "docs": DOCS.get(r.name, {}), "stats": st, "edges": edges, "verdict": _verdict_x(st), "nav": nav, **xp[i]})
    for k in prules:
        st = {s: {**ps[s][k], "label": P_SETTINGS[s][0]} for s in P_SETTINGS}
        edges = {s: {"dates": st[s].pop("dates"), "edge": st[s].pop("edges")} for s in ("us10", "early10")}
        pages.append({"kind": "payments", "name": k, "family": "payments", "generated": generated, "docs": DOCS.get(k, {}),
                      "stats": st, "edges": edges, "verdict": _verdict_p(st), "nav": nav, **pp[k]})
    return pages


def render_page(d: dict) -> str:
    page = (WEB / "dca_rule.html").read_text(encoding="utf-8")
    data = json.dumps(d, default=float).replace("</", "<\\/")
    # top nav (also the phone tab bar, <html data-nexus-tabs="page">): report, combined strategy, this rule
    # the first combined strategy's page (combined-strategy.html) also compares all four
    first = d.get("family") == "combined" and d.get("variant", "combined-strategy") == "combined-strategy"
    label = d.get("nav_label") or "Rule"
    active = ' class="active"' if first else ""
    nav = ('<a data-nexus-icon="bars" href="../report.html">DCA timing</a>'
           f'<a data-nexus-icon="target" href="combined-strategy.html"{active}>Combined strategies</a>'
           + ("" if first else f'<a data-nexus-icon="doc" href="#" class="active">{html.escape(label)}</a>'))
    return (page.replace("/*__SHAPES_CSS__*/", (WEB / "shapes.css").read_text(encoding="utf-8"))
                .replace("__NAV__", nav).replace("__TITLE__", html.escape(d["name"])).replace("__DATA__", data))


def write_pages(pages: list[dict], run_dir: str | Path) -> dict[str, str]:
    """Write ``rules/<slug>.html`` for every page; returns {rule name: path relative to the report}."""
    out = Path(run_dir) / "rules"
    out.mkdir(parents=True, exist_ok=True)
    links = {}
    for d in pages:
        (out / f"{slug(d['name'])}.html").write_text(render_page(d), encoding="utf-8")
        links[d["name"]] = page_href(d["name"])
    return links


# ---------------------------------------------------------------- the combined (continuous) strategies

def _pct(x, d=1):
    return f"{x * 100:+.{d}f}%"


def _debt(c) -> str:
    return "only Reg T (at most 2x)" if not np.isfinite(c.max_debt) else f"{c.max_debt:g} payments (${c.max_debt * 2000:,.0f})"


def _cell(r) -> str:
    return (f"{r['win']:.0%} · {_pct(r['median'])} · worst {_pct(r['worst'])} · fall {r['dd_vs_dca'] * 100:+.1f}" if r else "–")


def combined_page(c, cv: dict, attempts: list[dict] | None = None, generated: str | None = None, nav: list | None = None,
                  family: list[dict] | None = None) -> dict:
    """Page data for one combined strategy (:class:`perfectshape.dca.continuous.Kelly`): the rule-page sections plus
    the function itself (formula, parameters, a map of the exposure it asks for, today's calculation), the
    leave-one-era-out test (``cv``: one variant of research/dca/kelly4_cv.py), the earlier fits that failed
    (``attempts``) and the four combined strategies side by side (``family``)."""
    import pandas as pd
    from dataclasses import replace as dc_replace

    from perfectshape.dca.frontier import score
    from perfectshape.dca.report import FKEYS

    M = _markets()
    rule = c.rule()
    dip = c.signal == "dip"
    st, edges = {}, {}
    for key, (label, mk, years, kw) in X_SETTINGS.items():
        cfg = dc_replace(c.account(), **kw) if kw else c.account()
        r = score(M[mk], [rule], years, cfg, step=STEP, feats=M[f"f_{mk}"])[0]
        st[key] = {**{k: r[k] for k in FKEYS}, "label": label + " (fitted on all eras)"}
        if key in ("us10", "early10"):
            edges[key] = {"dates": [str(x) for x in r["start_dates"]], "edge": np.round(r["edges"], 5).tolist()}
    page = {"kind": "exposure", "name": rule.name, "family": "combined", "sell": c.sell,
            "generated": generated or datetime.now().strftime("%Y-%m-%d %H:%M"), "docs": COMBINED_DOCS[(c.signal, c.sell)],
            "stats": st, "edges": edges, "nav": nav or [], **path_data(rule, c.account())}
    # the honest test: each era scored by a strategy fitted on the other two
    cv_rows, wins, others = [], [], []
    for fold in cv["folds"]:
        res = fold["results"]
        comb = next(v for k, v in res.items() if k.startswith("Combined"))
        rest = [k for k in res if not k.startswith("Combined")]
        others = others or rest
        kf, fc = fold["kelly"], fold["forecast"]
        wins.append(comb)
        fc_txt = (f"{fc['p_dip_raw']:+.3f} per unit of drawdown beyond {fc['d_mean']:.0%} (t {fc['t_dip']:.1f})"
                  f"{', floored at 0' if fc['p_dip_raw'] < 0 else ''}, a {fc['a']:.3f}" if dip
                  else f"above {_pct(fc['p_above'])}, below {_pct(fc['p_below'])}, a {fc['a']:.3f}")
        size = f"k {kf.k:g}, debt {_debt(kf)}" + ("" if c.sell else f", cash {kf.max_cash:g}")
        cv_rows.append([fold["test"], ", ".join(fold["train"]), fc_txt, size, _cell(comb)] + [_cell(res.get(k)) for k in others])
    page["verdict"] = _verdict_cv(cv, wins, c)
    ablation = None
    if cv.get("ablation"):
        ab = cv["ablation"]
        ablation = {"head": ["Tested on", "As fitted", "Dip term only (no rate penalty)", "Rate term only (dip slope 0)"],
                    "rows": [[r["test"]] + [_cell(r[k]) for k in ("as fitted", "dip only", "rates only")] for r in ab]}
        dip_won = [r["test"] for r in ab if r["dip only"]["median"] > 0.005]
        page["verdict"] += (" Most of this edge is not from buying dips: with the rate term switched off, the dip term alone "
                            f"added something only in {', '.join(dip_won) if dip_won else 'no era'}; the rest comes from "
                            "borrowing after the 10-year yield has fallen and holding back after it has risen (table below).")
    # today's calculation, step by step (the last close's signals: what the next close trades on)
    f = M["f_us"]
    g = f.iloc[[-1]]
    mu, sig, e_b, e_l, e = (float(np.asarray(x)[0]) for x in c.parts(g))
    row = g.iloc[0]
    r2 = lambda x: f"{x * 100:.2f}%"
    now = {"date": str(f.index[-1].date()), "trend": float(row["trend"]), "dd": float(row["dd_ath"]), "vix": float(row["vix_like"]),
           "vol_long": float(row["vol_long"]), "y10": float(row["y10"]), "y3m": float(row["y3m"]), "y10_chg": float(row["y10_chg"]),
           "mu": mu, "sigma": sig, "e_b": e_b, "e_l": e_l, "target": e}
    rows = [["Signals of the close of", now["date"]]]
    rows += ([["S&P 500 below its all-time high", _pct(now["dd"])], ["Volatility of the last 10 years", f"{now['vol_long']:.1f}%"]] if dip
             else [["S&P 500 vs its 200-day average", _pct(now["trend"])], ["VIX", f"{now['vix']:.1f}"]])
    rows += [["10-year yield (the margin rate)", f"{now['y10']:.2f}%"], ["3-month bill (the Fed's rate)", f"{now['y3m']:.2f}%"],
             ["10-year yield, change over 6 months", f"{now['y10_chg']:+.2f} points"],
             ["Expected S&P 500 return a year (mu)", r2(mu)],
             [f"Volatility (sigma, {'10-year realised' if c.vol == 'long' else 'from the VIX'})", r2(sig)],
             *([["Dip's extra return a year (x)", r2(float(np.asarray(c.extra(g))[0]))], ["1 + k x x / s2", f"{e_b:.2f}"]] if dip
               else [["Borrow side E_b", f"{e_b:.2f}"], ["Cash side E_l", f"{e_l:.2f}"]]),
             ["<strong>Target exposure</strong>", f"<strong>{e:.2f}</strong>"]]
    # the map, at today's yields but no rate rise (so its shape shows; today's rise is in the step-by-step table)
    base = {"y10": row["y10"], "y3m": row["y3m"], "y10_chg": 0.0, "curve": row["curve"], "trend": row["trend"],
            "dd_ath": row["dd_ath"], "vix_like": row["vix_like"], "vol_long": row["vol_long"]}
    if dip:
        xs, xk, xl = np.round(np.arange(0.0, -0.5001, -0.025), 3), "dd_ath", "S&P 500 below its all-time high"
        ys, yk, yl = np.arange(10.0, 30.01, 1.0), "vol_long", "volatility of the last 10 years (%)"
        today = [max(-0.5, now["dd"]), now["vol_long"]]
        fmt = {"x": ".0%", "y": ".0f"}
    else:
        xs, xk, xl = np.arange(8, 45.1, 1.0), "vix_like", "VIX"
        ys, yk, yl = np.round(np.arange(-0.20, 0.2001, 0.02), 3), "trend", "S&P 500 vs 200-day average"
        today = [now["vix"], max(-0.2, min(0.2, now["trend"]))]
        fmt = {"x": ".0f", "y": "+.0%"}
    grid = pd.DataFrame([{**base, yk: y, xk: x} for y in ys for x in xs])
    z = np.round(np.asarray(c.parts(grid)[4], dtype=float).reshape(len(ys), len(xs)), 3).tolist()
    head = (f"Exposure the function asks for, by {xl.split(' (')[0]} and {yl.split(' (')[0]} (10-year {now['y10']:.2f}%, bill "
            f"{now['y3m']:.2f}%, no rate rise; x = today, whose rate rise of {now['y10_chg']:+.2f} points changes it)")
    page["combined"] = {"eyebrow": f"Combined strategy · a continuous Kelly function · {'sells to reach its target' if c.sell else 'never sells'}",
                        "now": now, "now_rows": rows, "formula": _formula(c), "params": _params(c, cv["forecast_all"]),
                        "map": {"x": xs.tolist(), "y": ys.tolist(), "z": z, "xlabel": xl, "ylabel": yl, "today": today,
                                "fmt": fmt, "head": head},
                        "cv": {"head": ["Tested on", "Fitted on", "Forecast estimated", "Sizing chosen", "Combined"] + others,
                               "rows": cv_rows,
                               "note": ("Each cell: beats plain DCA in · median edge · worst account · median fall against plain DCA "
                                        "(points; + = shallower). The two simple rules run with the same debt and cash caps and "
                                        f"{'sell' if c.sell else 'never sell'} too.")},
                        "attempts": attempts or [], "family": family or [], "ablation": ablation}
    return page


def _formula(c) -> str:
    if c.signal == "dip":
        floor = ("between 0 and 2; sells to reach it" if c.sell else "at least 1, at most 2; never sells" if c.max_cash <= 0
                 else f"at most 2; below 1 it holds back up to {c.max_cash:g} payments; never sells")
        return (f"dip's extra return  x = {c.p_dip:.3f} x (depth - {c.d_mean:.1%}) - {c.a:.3f} x (6-month rise of y10, points)\n"
                f"                    depth = how far the S&P 500 is below its all-time high, counted up to {c.dip_cap:.0%};\n"
                f"                    {c.d_mean:.1%} = its average since 1928 (so x > 0 only in deeper-than-usual falls)\n"
                f"variance            s2 = (realised volatility of the last 10 years)^2\n"
                f"exposure            1 + {c.k:g} x x / s2      a Kelly bet on the dip's extra return, on top of plain DCA; {floor}\n"
                f"                    (a falling 10-year yield makes x positive too: it then borrows without any dip)\n"
                f"limits              debt at most {_debt(c)}")
    else:
        mu = (f"expected return   mu = y10 + {_pct(c.p_below)} + ({_pct(c.p_above)} - {_pct(c.p_below)}) x w - {c.a:.3f} x (6-month rise of y10, points)\n"
              f"                  w = (1 + tanh(distance from the 200-day average / {c.width:.0%})) / 2   (0 well below, 1 well above)\n")
    var = "(realised volatility of the last 10 years)^2" if c.vol == "long" else "(VIX / 100)^2"
    if c.sell:
        tail = ("exposure          E_b if E_b > 1 (borrow); E_l if E_l < 1 (sell into T-bills); otherwise 1; between 0 and 2\n"
                f"limits            debt at most {_debt(c)}; sells to reach the target")
    else:
        tail = ("exposure          E_b if E_b > 1 (borrow); E_l if E_l < 1 (hold payments in cash); otherwise 1; at most 2\n"
                f"limits            debt at most {_debt(c)}, cash at most {c.max_cash:g} payments; never sells")
    return (mu + f"variance          s2 = {var}\n"
            f"borrow side       E_b = {c.k:g} x (mu - y10) / s2      stocks against the margin rate\n"
            f"cash side         E_l = {c.k:g} x (mu - y3m) / s2      stocks against T-bills (the Fed's rate)\n" + tail)


def _params(c, fc) -> list[list[str]]:
    if c.signal == "dip":
        rows = [["p_dip", f"{c.p_dip:.3f}", f"extra expected return a year per unit of drawdown beyond the usual (least squares on "
                                            f"{fc['months']} months, 1928-today; t = {fc['t_dip']:.1f}: weak evidence; at least 0)"],
                ["usual depth", f"{c.d_mean:.1%}", "the S&P 500's average distance below its all-time high, 1928-today"],
                ["p0", _pct(c.p0), "the S&P 500's average return over the 10-year yield (shown in mu; the overlay does not use it)"]]
    else:
        rows = [["p_above", _pct(c.p_above), f"S&P 500 over the 10-year yield, months starting above the average ({fc['months']} months, 1928-today)"],
                ["p_below", _pct(c.p_below), "the same for months starting below the average"]]
    rows += [["a", f"{c.a:.3f}", "expected return lost per point the 10-year yield rose over 6 months"],
             ["k", f"{c.k:g}", "Kelly fraction: the share of the theoretically optimal bet (chosen on the accounts)"],
             ["max debt", _debt(c), "the most debt allowed (chosen on the accounts)"]]
    if not c.sell:
        rows.append(["max cash", f"{c.max_cash:g} payments", "the most payments held back (chosen on the accounts)"])
    return rows


def _verdict_cv(cv, folds, c) -> str:
    n = sum(f["n"] for f in folds)
    won = sum(f["win"] * f["n"] for f in folds)
    parts = [f"{fo['test']}: {f['win']:.0%} ({_pct(f['median'])}, fall {f['dd_vs_dca'] * 100:+.1f} points)" for fo, f in zip(cv["folds"], folds)]
    calls = sum(f["calls"] for f in folds)
    return ("Each era was scored by a version fitted only on the other two (leave-one-era-out), so these numbers are out of "
            f"sample: it beat plain DCA in {won / max(n, 1):.0%} of {n} ten-year accounts - " + "; ".join(parts) + ". "
            "The strategy shown below is the same recipe fitted on all three eras, the version to use from today. "
            f"{'It sells to reach its target' if c.sell else 'It never sells'}; "
            f"{'no margin call in any test' if calls == 0 else f'{calls} margin calls in the tests'}.")


def family_rows(cvs: dict, finals: dict, nav_names: dict, current: str) -> list[dict]:
    """The four combined strategies side by side: pooled out-of-sample results, per era, and today's target."""
    M = _markets()
    g = M["f_us"].iloc[[-1]]
    out = []
    for slug_, cv in cvs.items():
        rs = [next(v for k, v in fo["results"].items() if k.startswith("Combined")) for fo in cv["folds"]]
        n = sum(r["n"] for r in rs)
        out.append({"name": nav_names[slug_], "href": f"{slug_}.html", "current": slug_ == current,
                    "win": sum(r["win"] * r["n"] for r in rs) / max(n, 1), "n": n,
                    "eras": [[fo["test"], _cell(r)] for fo, r in zip(cv["folds"], rs)],
                    "today": float(np.asarray(finals[slug_].parts(g)[4])[0])})
    return out


COMBINED_DOCS = {
    ("trend", False): {
        "what": "One continuous borrowing function instead of on/off rules: how much to borrow (or how many payments to hold "
                "back) follows the trend, the VIX, the margin rate (10-year yield) and the Fed's rate (3-month bill) every day. "
                "The account never sells: it only borrows more or less, and the monthly payments repay the debt.",
        "how": "Each day, from the previous close: expected S&P 500 return = 10-year yield + a premium that moves smoothly from "
               "its below-the-average value to its above-the-average value as the index crosses its 200-day average, minus a "
               "penalty for a rising 10-year yield. Merton's rule turns that into an exposure: k x (expected return - rate) / "
               "variance, the variance from the VIX. Against the margin rate (the 10-year yield) it says whether to borrow, "
               "against the bill rate (the Fed's rate) whether to hold payments in cash. Debt is capped in payments. The two "
               "premiums and the penalty are averages of monthly returns since 1928; k and the caps were chosen on the "
               "10-year accounts; the test below fits each era without it.",
        "idea": "Optimism: borrow when the market is rising calmly, the expected reward for risk is high and the loan is "
                "cheap; borrow less when it is nervous (high VIX means each borrowed dollar carries more risk) or rates are "
                "rising. The textbook (Merton / Kelly) answer to 'how much should I invest', with the research's findings "
                "(trend, rate shocks) as the forecast.",
        "risk": "Never selling means debt taken before a crash is carried through it, repaid only as fast as the payments "
                "allow: the debt cap in payments is what keeps this survivable. The forecast is crude, and the fitted numbers "
                "rest on three eras, a handful of independent decades. With k small it borrows rarely and adds a little over "
                "ten years. A no-sell account that holds no cash cannot fall less than plain DCA.",
    },
    ("dip", False): {
        "what": "The mirror image: a continuous function that borrows more the further the S&P 500 is below its all-time "
                "high, and less when the 10-year yield (the margin rate) is rising. The account never sells: payments repay "
                "the debt.",
        "how": "Each day, from the previous close: the dip's extra expected return = a slope times how much deeper the fall "
               "is than the usual one (the S&P 500 has been 17% below its high on average since 1928; depth counted up to "
               "40%), minus a penalty for a rising 10-year yield; both fitted by least squares on monthly returns, the slope "
               "at least zero. The exposure is plain DCA plus a Kelly bet on that extra return alone: 1 + k x extra / "
               "variance, the variance from the last 10 years' realised volatility (the VIX would veto every dip: it is "
               "highest exactly then). Debt is capped in payments; k and the caps were chosen on the 10-year accounts.",
        "idea": "Pessimism: stocks are cheaper after a fall, so the expected return should be higher; buy more when others "
                "are scared, with borrowed money, and let the payments repay it as the market recovers.",
        "risk": "The dip premium is weak: its slope has a t-statistic around 0.5 on all the data and is zero or negative "
                "in one of the three fits. Tested alone, the dip term helped only in 1928-1961; in the other eras the edge "
                "came from the rate term (borrow after yields fell, hold back after they rose). Debt carried through a long "
                "bear market (no selling) is what hurts; the cap in payments keeps it survivable.",
    },
    ("trend", True): {
        "what": "The optimism function, allowed to sell: it borrows in calm uptrends and sells into T-bills when the expected "
                "reward over the Fed's rate is too small for the risk, for example below the 200-day average in a nervous market.",
        "how": "The same forecast and Kelly sizing as the never-selling optimism strategy, but the account trades to its "
               "target both ways: above 1 it borrows, below 1 it sells shares into 3-month bills, down to nothing. Debt is "
               "capped in payments or only by Reg T margin (chosen on the accounts).",
        "idea": "Selling is what lets an account fall less than plain DCA: the trend and the VIX together point to the "
                "stretches when stocks paid the least for their risk.",
        "risk": "Every sale is a bet that the market will not rebound first; trend signals whipsaw in sideways markets, and "
                "each round trip costs. Sales may be taxed in a real account (not modelled).",
    },
    ("dip", True): {
        "what": "The pessimism function, allowed to sell: it borrows in deep falls and sells into T-bills near the highs when "
                "the expected reward over the Fed's rate is small for the risk.",
        "how": "The same overlay as the never-selling pessimism strategy, 1 + k x (the dip's extra return) / variance, but "
               "the account trades to its target both ways: in deeper-than-usual falls it borrows, near the highs (shallower "
               "than usual, or when the 10-year yield jumps) it sells shares into 3-month bills. Debt is capped in payments "
               "or only by Reg T margin (chosen on the accounts).",
        "idea": "Contrarian: hold less at the top, more after a fall. If dips are cheaper, the account buys low and sells "
                "high by construction.",
        "risk": "Markets spend most of their time near their highs, so a contrarian account is often under-invested in a "
                "rising market; and it buys all the way down a long bear market. Tested alone, the dip term helped only in "
                "1928-1961; the rest of the edge is the rate term. Sales may be taxed (not modelled).",
    },
}
