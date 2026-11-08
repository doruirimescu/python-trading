import numpy as np
import pandas as pd
import pytest

from tradelab.data import get_instrument, tag_sessions
from tradelab.features import (absorption, atr, confirmed_swings, delta_features, developing_value_area, fib_zone,
                               impulse_leg, market_structure, price_location, prior_session_levels, profile_levels,
                               retracement_price, session_vwap, zone_outside_value)

ET = "America/New_York"


def bars_from(prices, vols, day="2024-01-02", start="09:31", step=1):
    """one-price bars (low=high=open=close=price) -> volume histogram by price."""
    idx = pd.date_range(pd.Timestamp(f"{day} {start}", tz=ET), periods=len(prices), freq=f"{step}min").tz_convert("UTC")
    df = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": vols}, index=idx, dtype=float)
    return df


def test_profile_levels_hand_computed():
    # bar A spans 10..12 (30 vol -> 10 each), bar B at 11 (50)
    poc, vah, val = profile_levels(np.array([10.0, 11.0]), np.array([12.0, 11.0]), np.array([30.0, 50.0]), 1.0, 0.7)
    assert (poc, vah, val) == (11.0, 11.0, 11.0)               # 60/80 = 75% >= 70% at POC alone
    # classic diamond: volumes at prices 1..5 = 10,20,40,20,10; 70% VA -> 40+20(up, tie -> upper)+20 = 80
    p = np.arange(1.0, 6.0)
    v = np.array([10, 20, 40, 20, 10.0])
    poc, vah, val = profile_levels(p, p, v, 1.0, 0.7)
    assert (poc, vah, val) == (3.0, 4.0, 2.0)
    poc, vah, val = profile_levels(p, p, v, 1.0, 1.0)
    assert (vah, val) == (5.0, 1.0)


def test_prior_session_levels_join_and_causality():
    spec = get_instrument("MNQ")
    d1 = bars_from([1, 2, 3, 3, 3, 4, 5], [10, 20, 40, 0, 0, 20, 10], day="2024-01-02", start="09:31")
    d2 = bars_from([10, 11, 12], [5, 5, 5], day="2024-01-03", start="09:31")
    d3 = bars_from([20, 21], [5, 5], day="2024-01-04", start="09:31")
    df = tag_sessions(pd.concat([d1, d2, d3]), spec, "1m")
    lv = prior_session_levels(df, 1.0, 0.7)
    assert lv["prior_vah"].iloc[:7].isna().all()               # first session has no prior
    assert (lv["prior_poc"].iloc[7:10] == 3).all() and (lv["prior_vah"].iloc[7:10] == 4).all() and (lv["prior_val"].iloc[7:10] == 2).all()
    assert (lv["prior_poc"].iloc[10:] == 11).all()             # session 3 sees session 2 (not 1)
    # changing session 2 must not alter session 2's own prior levels (no same-session leakage)
    df2 = df.copy()
    df2.iloc[7:10, df2.columns.get_loc("volume")] = [1000, 1, 1]
    lv2 = prior_session_levels(df2, 1.0, 0.7)
    pd.testing.assert_series_equal(lv["prior_poc"].iloc[:10], lv2["prior_poc"].iloc[:10])
    assert lv2["prior_poc"].iloc[10] != lv["prior_poc"].iloc[10]


def test_developing_value_area_is_prefix_consistent():
    spec = get_instrument("MNQ")
    rng = np.random.default_rng(0)
    pr = np.round(100 + np.cumsum(rng.normal(0, 1, 60))).astype(float)
    df = tag_sessions(bars_from(pr, rng.integers(1, 50, 60)), spec, "1m")
    full = developing_value_area(df, 1.0)
    for k in (10, 30, 59):
        part = developing_value_area(df.iloc[: k + 1], 1.0)
        np.testing.assert_allclose(part.iloc[-1].to_numpy(), full.iloc[k].to_numpy())
    vah, val = full["dev_vah"].iloc[-1], full["dev_val"].iloc[-1]
    poc, vah2, val2 = profile_levels(df.low.to_numpy(), df.high.to_numpy(), df.volume.to_numpy(), 1.0, 0.7)
    assert (full["dev_poc"].iloc[-1], vah, val) == (poc, vah2, val2)       # final developing == full profile


def test_confirmed_swings_lag_and_values():
    #            0   1   2   3   4   5   6   7   8
    high = pd.Series([1, 2, 3, 9, 4, 3, 2, 8, 1.0])
    low = pd.Series([0, 1, 2, 3, 2, 1, 0.5, 1.5, 0.8])
    sw = confirmed_swings(high, low, k=2)
    # swing high at bar 3 (9) confirmed only at bar 5 ; before that NaN
    assert sw["last_swing_high"].iloc[:5].isna().all()
    assert sw["last_swing_high"].iloc[5] == 9 and sw["last_swing_high_pos"].iloc[5] == 3
    assert bool(sw["swing_high_new"].iloc[5]) and not sw["swing_high_new"].iloc[:5].any()
    # pivot at bar 7 (8) needs bars 8,9 -> not confirmed in this 9-bar series
    assert sw["last_swing_high"].iloc[-1] == 9
    # swing low at bar 6 (0.5) is confirmed at bar 8
    assert sw["last_swing_low"].iloc[8] == 0.5 and sw["last_swing_low"].iloc[7] != 0.5


def test_swings_prefix_invariance_random():
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 1, 300))
    h, l = pd.Series(c + rng.uniform(0, 1, 300)), pd.Series(c - rng.uniform(0, 1, 300))
    full = confirmed_swings(h, l, 3)
    part = confirmed_swings(h.iloc[:200], l.iloc[:200], 3)
    pd.testing.assert_frame_equal(full.iloc[:200], part)


def test_market_structure_and_fib():
    high = pd.Series([1, 3, 2, 5, 3, 4, 3, 6, 4, 5.0, 4.5, 4.4, 4.3])
    low = pd.Series([0, 1, 0.5, 2, 1.5, 3, 2.5, 4, 3, 3.5, 3.2, 3.1, 3.0])
    sw = confirmed_swings(high, low, 1)
    ms = market_structure(sw)
    assert ms.isin([-1, 0, 1]).all() and ms.iloc[-1] in (-1, 0, 1)
    leg = pd.DataFrame({"direction": [1, -1, 0], "leg_low": [100.0, 100, 100], "leg_high": [200.0, 200, 200]})
    assert retracement_price(100, 200, 1, 0.705) == pytest.approx(129.5)
    z = fib_zone(leg, 0.705, 0.886)
    assert z["zone_lo"].iloc[0] == pytest.approx(111.4) and z["zone_hi"].iloc[0] == pytest.approx(129.5)
    # down-leg mirrored: low + level*range
    assert z["zone_lo"].iloc[1] == pytest.approx(170.5) and z["zone_hi"].iloc[1] == pytest.approx(188.6)
    assert z.iloc[2].isna().all()
    out = zone_outside_value(z["zone_lo"], z["zone_hi"], pd.Series([130.0, 120, 100]), pd.Series([150.0, 150, 150]))
    assert out.tolist() == [True, True, False]   # idx1: down-leg zone sits above VAH (premium)
    assert zone_outside_value(pd.Series([111.4]), pd.Series([129.5]), pd.Series([100.0]), pd.Series([150.0])).tolist() == [False]  # zone inside value
    loc = price_location(pd.Series([90.0, 110, 160]), pd.Series([100.0] * 3), pd.Series([150.0] * 3))
    assert loc.tolist() == [-1.0, 0.0, 1.0]


def test_impulse_leg_direction():
    high = pd.Series([1, 2, 3, 9, 4, 3, 2, 1.0])
    low = pd.Series([0, 1, 2, 3, 2, 1, 0.5, 0.2])
    sw = confirmed_swings(high, low, 2)
    leg = impulse_leg(sw)
    assert leg["direction"].iloc[5] in (0, -1, 1)


def test_delta_real_vs_approx_label():
    spec = get_instrument("MNQ")
    df = tag_sessions(bars_from([10, 11, 12], [100, 100, 100]), spec, "1m")
    df["high"] += 1
    df["low"] -= 1
    f = delta_features(df)
    assert f["delta_is_approx"].all() and f.attrs["delta_source"] == "approx_delta"
    df["ask_vol"], df["bid_vol"] = [70.0, 20, 50], [30.0, 80, 50]
    f = delta_features(df)
    assert not f["delta_is_approx"].any() and f["delta"].tolist() == [40, -60, 0]
    assert f["cum_delta"].tolist() == [40, -20, -20]
    assert f.attrs["delta_source"] == "real"


def test_absorption_flags_real_delta():
    spec = get_instrument("MNQ")
    df = tag_sessions(bars_from([100.0, 100, 100], [100, 100, 100]), spec, "1m")
    df["open"], df["high"], df["low"], df["close"] = [100.0, 100, 100], [101.0, 101, 101], [95.0, 95, 99], [100.5, 96, 100.5]
    df["ask_vol"], df["bid_vol"] = [30.0, 30, 60], [70.0, 70, 40]
    a = absorption(df, wick_min=0.4, delta_pct_min=0.1)
    # bar0: sellers (delta -40%) pushed into long lower wick and closed up => absorption; bar1 closes at lows => no; bar2 delta +
    assert a["abs_long"].tolist() == [True, False, False]
    assert not a["delta_is_approx"].any()


def test_vwap_resets_each_session_and_atr_causal():
    spec = get_instrument("MNQ")
    d1 = bars_from([10, 12], [1, 3], day="2024-01-02")
    d2 = bars_from([20, 22], [1, 1], day="2024-01-03")
    df = tag_sessions(pd.concat([d1, d2]), spec, "1m")
    v = session_vwap(df)
    assert v.iloc[1] == pytest.approx((10 * 1 + 12 * 3) / 4) and v.iloc[2] == 20
    rng = np.random.default_rng(2)
    c = pd.Series(100 + np.cumsum(rng.normal(0, 1, 100)))
    h, l = c + 1, c - 1
    a = atr(h, l, c, 14)
    pd.testing.assert_series_equal(a.iloc[:60], atr(h.iloc[:60], l.iloc[:60], c.iloc[:60], 14))


def _leg_data():
    # up-leg 100 -> 120 (swing low at 2, swing high at 6), shallow pullback to 116 (swing low at 10), then continuation
    hi = np.array([102, 101, 100.5, 105, 110, 115, 120, 118, 117, 116.5, 116, 117, 118, 119, 121, 122.0])
    lo = np.array([101, 100.5, 100, 103, 108, 112, 118, 116, 115, 115, 114, 115, 116, 117, 119, 120.0])
    return pd.Series(hi), pd.Series(lo)


def test_impulse_leg_documented_semantics_up_leg_survives_small_pullback_pivot():
    high, low = _leg_data()
    sw = confirmed_swings(high, low, 2)
    # default (no size filter): the pullback low's confirmation flips the output to the pullback down-leg
    flip = impulse_leg(sw)
    assert flip["direction"].iloc[8] == 1 and (flip["leg_low"].iloc[8], flip["leg_high"].iloc[8]) == (100.0, 120.0)
    assert (flip["direction"] == -1).any()
    # with a min size the 4-point pullback leg is not an impulse leg: the up-leg persists
    leg = impulse_leg(sw, min_size=10.0)
    assert (leg["direction"] != -1).all()
    first = leg.index[leg["direction"] == 1][0]
    assert first == 8                                    # swing high at pos 6 is confirmed at bar 6+k
    assert (leg.loc[first:, "leg_low"] == 100.0).all() and (leg.loc[first:, "leg_high"] == 120.0).all()
    assert (leg.loc[:first - 1, "direction"] == 0).all()
    # series min size evaluated at the confirmation bar (e.g. multiple of ATR)
    leg2 = impulse_leg(sw, min_size=pd.Series(10.0, index=high.index))
    pd.testing.assert_frame_equal(leg, leg2)
    # direction filter
    assert (impulse_leg(sw, direction="down")["direction"] != 1).all()


def test_impulse_leg_is_causal_prefix_invariant():
    high, low = _leg_data()
    full = impulse_leg(confirmed_swings(high, low, 2), min_size=10.0)
    for T in range(6, len(high)):
        pre = impulse_leg(confirmed_swings(high.iloc[:T], low.iloc[:T], 2), min_size=10.0)
        pd.testing.assert_frame_equal(pre, full.iloc[:T])
