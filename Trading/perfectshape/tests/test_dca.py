"""DCA study: the account's rules (caps, interest, margin), policies that cannot see the future, the evaluation
over start months and the report."""

import numpy as np
import pandas as pd
import pytest

from perfectshape.dca.account import AccountConfig, best_possible, pay_days, simulate
from perfectshape.dca.data import frame_from_prices
from perfectshape.dca.evaluate import compare, windows
from perfectshape.dca.policy import const, to_array, trend_policy, trend_state, turn_of_month, vote_policy, when
from perfectshape.dca.signals import features
from perfectshape.dca.strategy import RECOMMENDED, Strategy, decision


def make_market(years=16, seed=5, drift=0.0004, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("1990-01-02", periods=252 * years)
    px = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, vol, len(idx)))), index=idx)
    y10 = pd.Series(4.0 + np.cumsum(rng.normal(0, 0.02, len(idx))).clip(-2, 4), index=idx)
    return frame_from_prices(px, y10, y3m=y10 - 1.0)


def flat(n_months=30, price=100.0, y10=6.0, y3m=3.0):
    idx = pd.bdate_range("2001-01-01", periods=21 * n_months)
    dates = idx.values.astype("datetime64[D]")
    return np.full(len(idx), price), dates, np.full(len(idx), y10), np.full(len(idx), y3m)


def test_pay_days_are_first_trading_days():
    dates = pd.bdate_range("2024-01-01", "2024-03-29").values.astype("datetime64[D]")
    pay = pay_days(dates)
    assert pay.sum() == 3 and [str(d) for d in dates[pay]] == ["2024-01-01", "2024-02-01", "2024-03-01"]


def test_plain_dca_on_a_flat_price_keeps_what_was_paid():
    tr, dates, y10, y3m = flat()
    r = simulate(tr, dates, np.zeros(len(tr)), y10, y3m)
    n = pay_days(dates).sum()
    assert r["paid"][0] == 2000 * n and r["wealth"][0] == pytest.approx(2000 * n)
    assert r["cash"][0] == 0 and r["interest"][0] == 0 and r["shares"][0] == pytest.approx(20 * n)


def test_holding_respects_the_cap_and_earns_the_bill_rate():
    tr, dates, y10, y3m = flat()
    r = simulate(tr, dates, np.full(len(tr), 99.0), y10, y3m)
    assert r["max_cash"][0] <= 12000 + 1e-6 and r["min_cash"][0] == 0
    assert r["interest"][0] < 0                                   # interest received
    assert r["wealth"][0] > r["paid"][0]
    none = simulate(tr, dates, np.full(len(tr), 99.0), y10, y3m, AccountConfig(cash_earns=False))
    assert none["wealth"][0] == pytest.approx(none["paid"][0])


def test_borrowing_respects_the_cap_reg_t_and_costs_the_ten_year_yield():
    tr, dates, y10, y3m = flat()
    r = simulate(tr, dates, np.full(len(tr), -6.0), y10, y3m, path=True)
    pay = np.flatnonzero(pay_days(dates))
    cash = r["cash_path"]
    assert cash[pay[0]] == pytest.approx(-2000)                   # Reg T: a new account can borrow what it owns
    assert cash[pay[1]] < -3900 and r["min_cash"][0] >= -12000 * 1.01
    assert r["interest"][0] > 0 and r["wealth"][0] < r["paid"][0]
    year = 12000 * 0.06
    late = r["wealth_path"][pay[-13]] - r["wealth_path"][pay[-1]] + 12 * 2000    # a year at full debt on a flat price
    assert late == pytest.approx(year, rel=0.05)
    tight = simulate(tr, dates, np.full(len(tr), -6.0), y10, y3m, AccountConfig(initial_margin=0.9), path=True)
    pos = tight["wealth_path"] - tight["cash_path"]
    assert (-tight["cash_path"][pay[3]:] <= 0.1 * pos[pay[3]:] * 1.02).all()


def test_margin_call_sells_back_to_maintenance():
    tr, dates, y10, y3m = flat(n_months=6)
    tr = tr.copy()
    tr[70:] = 60.0                                                # -40% after the fourth payment
    r = simulate(tr, dates, np.full(len(tr), -6.0), y10, y3m, path=True)
    assert r["margin_calls"][0] >= 1
    pos = r["wealth_path"][70] - r["cash_path"][70]
    assert (r["wealth_path"][70] / pos) >= 0.30 - 1e-6
    assert simulate(tr, dates, np.zeros(len(tr)), y10, y3m)["margin_calls"][0] == 0


def test_many_start_dates_match_single_accounts():
    m = make_market(years=6)
    f = features(m)
    dates = m.index.values.astype("datetime64[D]")
    tg = to_array(trend_policy(100), f)
    w = windows(dates, 2)
    args = (m["tr"].to_numpy(), dates, tg, m["y10"].to_numpy(), m["y3m"].to_numpy())
    both = simulate(*args, starts=w.starts, ends=w.ends)
    assert len(w.starts) == pay_days(dates).sum() - 24
    for i in (0, 17, len(w.starts) - 1):
        one = simulate(*args, starts=w.starts[i:i + 1], ends=w.ends[i:i + 1])
        assert one["wealth"][0] == pytest.approx(both["wealth"][i], rel=1e-12)
        assert both["paid"][i] == 24 * 2000


def test_policies_use_yesterday_and_nothing_later():
    m = make_market(years=8)
    f = features(m)
    X = 1500
    m2 = m.copy()
    rng = np.random.default_rng(1)
    m2.iloc[X:, m2.columns.get_loc("px")] *= np.exp(np.cumsum(rng.normal(0, 0.03, len(m) - X)))
    m2.iloc[X:, m2.columns.get_loc("y10")] += 3.0
    f2 = features(m2)
    pols = [RECOMMENDED.policy(), trend_policy(200), trend_policy(150, band=0.01), vote_policy(2.0, tom=True),
            when(lambda g: g["dd"] < -0.05, -6, 3), turn_of_month(4)]
    for pol in pols:
        a, b = to_array(pol, f), to_array(pol, f2)
        np.testing.assert_array_equal(a[:X + 1], b[:X + 1])       # the trade at close X uses data up to X - 1
    assert not np.array_equal(to_array(RECOMMENDED.policy(), f)[X + 250:], to_array(RECOMMENDED.policy(), f2)[X + 250:])


def test_trend_policy_shapes():
    m = make_market(years=4)
    f = features(m)
    daily, monthly = to_array(trend_policy(200), f), to_array(trend_policy(200, monthly=True), f)
    assert set(np.unique(daily)) <= {-6.0, 0.0} and (daily[:200] == 0).all()
    per_month = pd.Series(monthly, index=m.index).groupby(m.index.to_period("M")).nunique()
    assert (per_month == 1).all()                                  # decided on payment day, kept for the month
    px = pd.Series([1.0] * 5 + [1.05, 1.004, 0.997, 0.90, 1.0])
    assert trend_state(px, 3, band=0.0).iloc[-1] == True          # noqa: E712
    banded = trend_state(px, 3, band=0.02)
    assert banded.iloc[5] == 1 and banded.iloc[7] == 1 and banded.iloc[8] == 0
    tom = to_array(turn_of_month(4), f)
    assert (tom[f["tdleft"].to_numpy() <= 4] == -1).all() and (tom[f["tdleft"].to_numpy() > 4] == 0).all()
    g = Strategy(guard_rise=0.05, guard_days=20)
    guarded = to_array(g.policy(), f)
    assert (guarded <= 0).all() and (guarded != to_array(Strategy(guard_days=0).policy(), f)).any()


def test_foresight_beats_fixed_policies_and_respects_the_caps():
    m = make_market(years=5, seed=11)
    dates = m.index.values.astype("datetime64[D]")
    args = (m["tr"].to_numpy(), dates)
    rates = (m["y10"].to_numpy(), m["y3m"].to_numpy())
    best = best_possible(*args, *rates)
    assert best.min() >= -6 and best.max() <= 6
    top = simulate(*args, best, *rates)["wealth"][0]
    for k in (0.0, -6.0, 6.0, -3.0):
        assert top >= simulate(*args, np.full(len(dates), k), *rates)["wealth"][0] - 1e-6


def test_compare_ranks_always_early_by_the_market():
    up, down = make_market(years=8, drift=0.0008), make_market(years=8, drift=-0.0004)
    for m, sign in ((up, 1), (down, -1)):
        f = features(m)
        out = compare(m, {"dca": to_array(const(0), f), "early": to_array(const(-6), f), "hold": to_array(const(6), f)}, 5)
        assert np.sign(out["early"]["median"]) == sign and np.sign(out["hold"]["median"]) == -sign
        months = pay_days(m.index.values.astype("datetime64[D]")).sum()
        assert out["early"]["n"] == months - 60 and 0 <= out["early"]["win"] <= 1


def test_decision_and_report(tmp_path):
    from perfectshape.dca.report import build_payload, render_html, summary_md, write_report

    m = make_market(years=16, drift=0.0006)
    n = decision(m, features(m), RECOMMENDED)
    assert n["date"] == str(m.index[-1].date()) and n["target"] in (-6.0, 0.0) and n["borrow"] == (n["above"] and not n["guarded"])
    p = build_payload(RECOMMENDED, quick=True, market=m)
    name = "Strategy: trend + rate guard"
    assert set(p["horizons"]) == {"5", "10"} and name in p["alternatives"] and p["early"] == {} and p["other"] == []
    assert p["alternatives"]["Hold 6 payments in cash"]["median"] < 0 < p["alternatives"]["Always 6 payments ahead"]["median"]
    assert len(p["edges10"][name]["edge"]) == p["horizons"]["10"][name]["n"] and p["savers"]
    assert "This month" in summary_md(p) and "__DATA__" not in render_html(p)
    x = p["exposure"]
    assert x["frontier"][0]["rule"] == x["name"] and len(x["frontier"]) > 15 and x["now"]["exposure"] in (0.5, 1.0, 1.5)
    assert [c["label"] for c in x["checks"]] == ["5-year accounts", "10-year accounts"]
    assert len(x["path"]["dd"]) == len(x["path"]["dates"]) and min(x["path"]["dd"]) < 0
    assert "Borrowing sized against the account" in summary_md(p)
    run_dir = write_report(p, tmp_path)
    assert {x.name for x in run_dir.iterdir()} == {"report.html", "summary.md", "dca.json"}


# ---------------------------------------------------------------- borrowing sized against the account

from perfectshape.dca.exposure import ExposureConfig, simulate_exposure  # noqa: E402
from perfectshape.dca.frontier import score  # noqa: E402
from perfectshape.dca.rules import Rule, both, flat as flat_rule, highest, ladder, only_if, rate_guard, switch, unless, vol_target  # noqa: E402
from perfectshape.dca.rules import trend as trend_rule  # noqa: E402

FREE = ExposureConfig(trade_cost=0.0)


def test_exposure_one_is_plain_dca():
    tr, dates, y10, y3m = flat()
    r = simulate_exposure(tr, dates, np.ones(len(tr)), y10, y3m, FREE)
    n = pay_days(dates).sum()
    assert r["wealth"][0] == pytest.approx(2000 * n) and r["max_dd"][0] == 0 and r["interest"][0] == 0
    assert r["avg_exposure"][0] == pytest.approx(1.0) and r["traded"][0] == pytest.approx(0.0)
    costly = simulate_exposure(tr, dates, np.ones(len(tr)), y10, y3m, ExposureConfig(trade_cost=0.001))
    assert costly["wealth"][0] == pytest.approx(2000 * n * 0.999)


def test_borrowing_a_share_of_the_account_and_two_ways_down():
    tr, dates, y10, y3m = flat(n_months=24)
    e = np.where(np.arange(len(tr)) < 300, 1.5, 1.0)
    sold = simulate_exposure(tr, dates, e, y10, y3m, FREE, sell=True, path=True)
    kept = simulate_exposure(tr, dates, e, y10, y3m, FREE, sell=False, path=True)
    assert sold["exposure_path"][250] == pytest.approx(1.5, abs=0.03) and kept["exposure_path"][250] == pytest.approx(1.5, abs=0.03)
    assert sold["exposure_path"][301] == pytest.approx(1.0, abs=0.03)        # sold to repay
    assert kept["exposure_path"][301] > 1.4                                     # never sells ...
    assert kept["exposure_path"][-1] < kept["exposure_path"][301] - 0.1        # ... the payments repay
    assert sold["interest"][0] > 0 and kept["interest"][0] > sold["interest"][0]
    assert sold["max_exposure"][0] <= 2.0 + 1e-9
    capped = simulate_exposure(tr, dates, np.full(len(tr), 5.0), y10, y3m, FREE, sell=True)
    assert capped["max_exposure"][0] == pytest.approx(2.0, abs=0.02)            # Reg T


def test_drawdown_ignores_payments_and_shrinks_with_cash():
    tr, dates, y10, y3m = flat(n_months=40)
    tr = tr.copy()
    tr[300:500] = np.linspace(100, 50, 200)
    tr[500:] = np.linspace(50, 100, len(tr) - 500)
    full = simulate_exposure(tr, dates, np.ones(len(tr)), y10, y3m, FREE)
    half = simulate_exposure(tr, dates, np.full(len(tr), 0.5), y10, y3m, FREE, sell=True)
    lev = simulate_exposure(tr, dates, np.full(len(tr), 1.5), y10, y3m, FREE, sell=True)
    assert full["max_dd"][0] == pytest.approx(-0.5, abs=0.005)                  # payments on the way down do not hide the fall
    assert -0.30 < half["max_dd"][0] < -0.20 and lev["max_dd"][0] < -0.60
    assert lev["margin_calls"][0] == 0 and not lev["wiped"][0]


def test_margin_call_and_wipe_out_at_full_leverage():
    tr, dates, y10, y3m = flat(n_months=12)
    tr = tr.copy()
    tr[100:] = 62.0
    r = simulate_exposure(tr, dates, np.full(len(tr), 2.0), y10, y3m, FREE, sell=False, path=True)
    assert r["margin_calls"][0] >= 1 and not r["wiped"][0]
    assert r["exposure_path"][100] <= 1 / 0.30 + 1e-6
    tr[100:] = 45.0
    gone = simulate_exposure(tr, dates, np.full(len(tr), 2.0), y10, y3m, FREE, sell=False)
    assert gone["wiped"][0] and gone["max_dd"][0] == pytest.approx(-1.0)


def test_rule_builders():
    idx = pd.bdate_range("2020-01-01", periods=12)
    f = pd.DataFrame({"px": 100.0, "dd_ath": [0, -0.05, -0.12, -0.25, -0.15, -0.08, -0.03, -0.01, -0.11, 0, 0, 0],
                      "vix": [15, 25, 31, 45, 28, 22, 19, 18, 35, np.nan, 12, 12],
                      "rv21": [10, 10, 30, 60, 20, 15, 10, 7.5, 15, 15, 15, 15],
                      "y10": 4.0, "tdom": 5, "tdleft": 10}, index=idx)
    lad = ladder([(-0.10, 0.10), (-0.20, 0.20)])(f).to_numpy()            # read one day late; holds until recovered
    np.testing.assert_allclose(lad, [1, 1, 1, 1.1, 1.2, 1.2, 1.2, 1.2, 1.0, 1.1, 1.0, 1.0])
    sw = switch("vix", 30, 20, 1.5)(f).to_numpy()
    np.testing.assert_allclose(sw, [1, 1, 1, 1.5, 1.5, 1.5, 1.5, 1, 1, 1.5, 1, 1])
    calm = switch("vix", 15, 20, 1.25)(f).to_numpy()
    np.testing.assert_allclose(calm, [1, 1.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.25])
    vt = vol_target(15, 0.5, 1.5, monthly=False)(f).to_numpy()
    np.testing.assert_allclose(vt, [1, 1.5, 1.5, 0.5, 0.5, 0.75, 1, 1.5, 1.5, 1, 1, 1])
    np.testing.assert_allclose(highest(flat_rule(1.1), switch("vix", 30, 20, 1.5))(f), np.maximum(1.1, sw))
    np.testing.assert_allclose(both(flat_rule(1.1), switch("vix", 30, 20, 1.5))(f), 0.1 + sw)
    guarded = unless(flat_rule(1.5), lambda g: g["vix"] > 30)(f).to_numpy()
    np.testing.assert_allclose(guarded, [1.5, 1.5, 1.5, 1, 1, 1.5, 1.5, 1.5, 1.5, 1, 1.5, 1.5])
    gated = only_if(flat_rule(1.5), lambda g: g["vix"] < 20)(f).to_numpy()
    np.testing.assert_allclose(gated, [1, 1.5, 1, 1, 1, 1, 1, 1.5, 1.5, 1, 1, 1.5])
    assert rate_guard(0.5, 1)(f.assign(y10=[4.0] * 6 + [4.6] + [4.6] * 5)).sum() == 1


def test_exposure_rules_do_not_look_ahead_and_score_against_dca():
    m = make_market(years=9, drift=0.0005)
    f = features(m)
    X = 1700
    m2 = m.copy()
    rng = np.random.default_rng(2)
    m2.iloc[X:, m2.columns.get_loc("px")] *= np.exp(np.cumsum(rng.normal(0, 0.03, len(m) - X)))
    f2 = features(m2)
    rules = [Rule("dca", flat_rule(1.0)), Rule("ladder", ladder([(-0.10, 0.2), (-0.20, 0.4)], confirm=50)),
             Rule("trend", unless(trend_rule(1.5, 0.5, monthly=True), rate_guard()), True),
             Rule("vol", only_if(vol_target(15, 1.0, 2.0), lambda g: g["trend"] > 0), True),
             Rule("spike", switch("rv_ratio", 1.5, 1.0, 1.25), True)]
    for r in rules:
        np.testing.assert_array_equal(r.array(f)[:X + 1], r.array(f2)[:X + 1])
    rows = score(m, rules, 5, step=6)
    by = {r["rule"]: r for r in rows}
    assert by["dca"]["median"] == 0 and by["dca"]["dd_vs_dca"] == 0 and by["dca"]["win"] == 0
    assert by["trend"]["avg_exposure"] != 1.0 and by["trend"]["turnover"] > by["ladder"]["turnover"] >= 0
    assert all(len(r["edges"]) == r["n"] == rows[0]["n"] for r in rows)


def test_every_report_rule_has_a_page_text():
    from perfectshape.dca.pages import DOCS, page_href, slug
    from perfectshape.dca.report import alternatives, frontier_rules
    from perfectshape.dca.strategy import EXPOSURE_RECOMMENDED

    names = [r.name for r in frontier_rules(EXPOSURE_RECOMMENDED)] + list(alternatives(RECOMMENDED))
    assert all(set(DOCS[n]) == {"what", "how", "idea", "risk"} for n in names)
    assert len({slug(n) for n in names}) == len(names) and page_href(names[0]).startswith("rules/")


def test_report_page_helpers_are_defined_before_use():
    """A const used before its declaration stops the page's script, leaving every box after it empty."""
    import re
    from pathlib import Path

    for name in ("dca.html", "dca_rule.html"):
        js = (Path(__file__).resolve().parents[1] / "src" / "perfectshape" / "web" / name).read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*const (\w+) = ", js, re.M):
            first_use = re.search(rf"(?<![\w.]){m.group(1)}\(", js)
            assert first_use is None or first_use.start() > m.start(), f"{name}: {m.group(1)} used before it is defined"


def test_debt_and_cash_caps_in_payments():
    tr, dates, y10, y3m = flat(n_months=24)
    r = simulate_exposure(tr, dates, np.full(len(tr), 2.0), y10, y3m, ExposureConfig(trade_cost=0.0, max_debt=3.0), path=True)
    assert np.asarray(r["wealth_path"]).min() >= 0 and r["margin_calls"][0] == 0
    cash = simulate_exposure(tr, dates, np.full(len(tr), 2.0), y10, y3m, ExposureConfig(trade_cost=0.0, max_debt=3.0))
    full = simulate_exposure(tr, dates, np.full(len(tr), 2.0), y10, y3m, ExposureConfig(trade_cost=0.0))
    assert cash["interest"][0] < full["interest"][0]
    held = simulate_exposure(tr, dates, np.zeros(len(tr)), y10, y3m, ExposureConfig(trade_cost=0.0, max_cash=2.0), path=True)
    assert held["avg_exposure"][0] > 0.5                         # payments beyond two are invested


def test_kelly_function_borrows_when_cheap_and_calm_and_never_looks_ahead():
    from perfectshape.dca.continuous import Kelly, estimate_kelly_forecast, month_table

    k = Kelly(p_above=0.09, p_below=0.01, a=0.08, k=0.15, max_debt=12, max_cash=0)
    g = pd.DataFrame({"trend": [0.05, 0.05, -0.05, 0.05], "vix_like": [10.0, 30.0, 10.0, 10.0], "y10": 4.0, "y3m": 3.0,
                      "y10_chg": [0.0, 0.0, 0.0, 1.0], "curve": 1.0})
    e = np.asarray(k.parts(g)[4])
    assert e[0] > 1.0 and e[1] == 1.0 and e[2] == 1.0 and e[3] == 1.0   # calm and above: borrow; otherwise plain DCA
    m = make_market(years=9, drift=0.0005)
    f = features(m)
    X = 1700
    m2 = m.copy()
    m2.iloc[X:, m2.columns.get_loc("px")] *= 0.7
    m2.iloc[X:, m2.columns.get_loc("y10")] += 2.0
    a, b = k.rule().array(f), k.rule().array(features(m2))
    np.testing.assert_array_equal(a[:X + 1], b[:X + 1])
    fc = estimate_kelly_forecast(month_table(m, f), ["1962-1999"])
    assert {"p_above", "p_below", "a"} <= set(fc) and fc["months"] > 50


def test_dip_kelly_borrows_more_the_deeper_the_fall_and_the_sell_versions_sell():
    from perfectshape.dca.continuous import VARIANTS, Kelly, estimate_dip_forecast, month_table

    g = pd.DataFrame({"dd_ath": [0.0, -0.1, -0.3, -0.6], "vol_long": 16.0, "vix_like": 60.0, "trend": -0.1, "y10": 4.0,
                      "y3m": 3.0, "y10_chg": 0.0})
    dip = Kelly(signal="dip", vol="long", p0=0.05, p_dip=0.3, d_mean=0.05, a=0.05, k=1.0, max_debt=12, max_cash=0)
    e = np.asarray(dip.parts(g)[4])
    assert e[0] == 1.0 and e[1] < e[2] <= e[3] and e[2] > 1.0      # deeper = more; the VIX does not veto it
    assert e[3] == pytest.approx(np.asarray(dip.parts(g.assign(dd_ath=-0.4))[4])[3])   # depth counted up to 40%
    sells = Kelly(signal="dip", vol="long", p0=0.05, p_dip=0.3, d_mean=0.05, k=1.0, sell=True)
    es = np.asarray(sells.parts(g)[4])
    assert es[0] < 1.0 < es[2] and sells.rule().sell and np.isinf(sells.account().max_cash)   # less at the high
    assert not Kelly().rule().sell and len({Kelly(signal=s, sell=x).title for s, _, x in VARIANTS.values()}) == 4
    m = make_market(years=9, drift=0.0005)
    f = features(m)
    X = 1700
    m2 = m.copy()
    m2.iloc[X:, m2.columns.get_loc("px")] *= 0.6
    a, b = dip.rule().array(f), dip.rule().array(features(m2))
    np.testing.assert_array_equal(a[:X + 1], b[:X + 1])
    fc = estimate_dip_forecast(month_table(m, f), ["1962-1999"])
    assert {"p0", "p_dip", "a", "t_dip"} <= set(fc)
