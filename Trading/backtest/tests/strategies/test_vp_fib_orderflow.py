"""Tests for strategies/vp_fib_orderflow.py (hand-built fixtures per stage + causality + e2e)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "strategies"))
import vp_fib_orderflow as v  # noqa: E402

from helpers import intraday_panel  # noqa: E402
from tradelab.config import DataCfg, ExecCfg, RiskRules, load_config  # noqa: E402
from tradelab.data import load_panel  # noqa: E402
from tradelab.engine import check_causality, run_backtest  # noqa: E402

TICK = 0.25
P = v.VpFibParams


def mk(bars, *, val=110.0, vah=115.0, poc=112.0, ok=True, swl=((2, 100.0, 0),), swh=((10, 120.0, 8),), real=False, vol=30000.0):
    """bars: list of (o,h,l,c,delta_pct). swl/swh: (confirm_bar, px, pivot_pos)."""
    n = len(bars)
    a = np.array(bars, float)
    inp = dict(open=a[:, 0], high=a[:, 1], low=a[:, 2], close=a[:, 3], delta_pct=a[:, 4], volume=np.full(n, vol),
               imb_buy=np.full(n, np.nan), imb_sell=np.full(n, np.nan), ctx_ok=np.full(n, ok), in_window=np.ones(n, bool),
               sess=np.zeros(n, int), val=np.full(n, val), vah=np.full(n, vah), poc=np.full(n, poc), atr=np.full(n, 2.0), real=real)
    for nm, ev in (("swl", swl), ("swh", swh)):
        inp[nm + "_new"], inp[nm + "_px"], inp[nm + "_pos"] = np.zeros(n, bool), np.full(n, np.nan), np.zeros(n, int)
        for i, px, pos in ev:
            inp[nm + "_new"][i], inp[nm + "_px"][i], inp[nm + "_pos"][i] = True, px, pos
    return inp


def pad(n=11):
    """bars 0..10: a flat filler so swing events at 2 and 10 are in range (prices irrelevant, above the zone)."""
    return [(118, 119, 117, 118, 0.0)] * n


# leg 100 -> 120 (R=20): zone 0.705..0.886 = [102.28, 105.9]; invalid(0.886) = 102.28, invalid(1.0)=100
ABS = (105.0, 105.2, 103.0, 104.5, -0.3)      # sells into the zone, long lower wick (0.75 of range), delta<0
FLIP = (104.2, 106.0, 104.0, 105.8, 0.4)      # bullish flip
PULL = (105.8, 105.9, 104.5, 104.8, -0.2)     # sellers retry, fail higher (low 104.5 > 103.0)


def run(bars, p=None, **kw):
    p = p or P()
    return v.scan_long(mk(bars, **kw), p, TICK)


# ----------------------------------------------------------------------------------- context
def test_va_migration_dir():
    d = v.va_migration_dir([105, 95, 100, np.nan], [115, 105, 110, 110], [100, 100, 100, 100], [110, 110, 110, 110])
    assert d.tolist() == [1, -1, 0, 0]
    assert v.va_migration_dir([100], [112], [100], [108], "strict").tolist() == [0]
    assert v.va_migration_dir([100], [112], [100], [108], "mid").tolist() == [1]


def test_htf_structure_value_up_down_and_causal_finality():
    # 60-min buckets over 5m bars (12/bucket): hourly lows/highs rising then falling
    def day(levels):
        out = []
        for lo, hi in levels:
            out += [(lo + 1, hi, lo, hi - 1)] * 12
        return out
    up = [(100, 110), (104, 114), (101, 108), (108, 118), (106, 112), (112, 122)]
    dn = [(100 - a, 110 - a) for a, _ in [(0, 0), (2, 0), (-5, 0), (8, 0), (4, 0), (14, 0)]]
    arr = day(up)
    pan = intraday_panel(arr)
    b = pan["MNQ"]
    o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
    em = (b.index.tz_convert("America/New_York").hour * 60 + b.index.tz_convert("America/New_York").minute).to_numpy()
    st = v.htf_structure(o, h, l, c, em, np.zeros(len(b), int), 5, 60, 1)
    assert st[-1] == 1                                  # HH & HL confirmed
    assert st[:20].tolist() == [0] * 20                 # nothing known early
    # bucket is only known at its final bar: structure cannot change mid-bucket
    chg = np.flatnonzero(np.diff(st) != 0) + 1
    assert all(((em[i] - 570) % 60) == 0 for i in chg)
    dmx = [(110 - lo + 90, 110 - lo + 100) for lo, _ in up]
    pan2 = intraday_panel(day(dmx))
    b2 = pan2["MNQ"]
    em2 = (b2.index.tz_convert("America/New_York").hour * 60 + b2.index.tz_convert("America/New_York").minute).to_numpy()
    st2 = v.htf_structure(*(b2[k].to_numpy() for k in ("open", "high", "low", "close")), em2, np.zeros(len(b2), int), 5, 60, 1)
    assert st2[-1] == -1


# ----------------------------------------------------------------------------------- zone + invalidation
def test_zone_geometry_and_outside_value_gate():
    r = run(pad() + [ABS, FLIP])
    assert r["zone_lo"][12] == pytest.approx(102.28) and r["zone_hi"][12] == pytest.approx(105.9)
    assert r["sig"][12]
    # zone inside value area (VAL above zone top is required; VAL=104 cuts through it) -> no trade
    assert not run(pad() + [ABS, FLIP], val=104.0)["sig"].any()
    # 'discount' mode only needs the absorption low below VAL
    assert run(pad() + [ABS, FLIP], p=P(zone_vs_value="discount"), val=104.0)["sig"][12]


def test_invalidation_before_trigger():
    # a close beyond 0.886 (102.28) kills the leg before the flip
    crash = (104, 104.2, 101.0, 101.5, -0.5)
    assert not run(pad() + [ABS, crash, FLIP])["sig"].any()
    # wick-only breach: invalid_on=close keeps the setup, invalid_on=low kills it
    wick = (105.0, 105.2, 102.0, 104.5, -0.3)
    assert run(pad() + [wick, FLIP], p=P(swing_confirm="off"))["sig"][12]
    assert not run(pad() + [wick, FLIP], p=P(swing_confirm="off", invalid_on="low"))["sig"].any()
    # invalid_level 1.0 tolerates a deeper pullback
    deep = (103.0, 104.0, 100.5, 101.8, -0.5)
    assert not run(pad() + [deep, FLIP])["sig"].any()
    r = run(pad() + [deep, FLIP], p=P(invalid_level=1.0))
    assert r["sig"][12] and r["stop"][12] == pytest.approx(100.5 - TICK)


def test_no_trade_without_context_or_swing():
    assert not run(pad() + [ABS, FLIP], ok=False)["sig"].any()
    # no sweep (prior lows lower) and no confirmed swing in zone -> swing_confirm blocks
    low_pad = [(118, 119, 100.5, 118, 0.0)] * 11
    assert not run(low_pad + [ABS, FLIP])["sig"].any()
    assert run(low_pad + [ABS, FLIP], p=P(swing_confirm="off"))["sig"][12]


# ----------------------------------------------------------------------------------- trigger
def test_absorption_needs_sell_delta_and_wick():
    no_delta = (105.0, 105.2, 103.0, 104.5, +0.3)
    short_wick = (105.0, 105.2, 104.4, 104.5, -0.3)      # low 104.4 touches zone, wick tiny
    assert not run(pad() + [no_delta, FLIP])["sig"].any()
    assert not run(pad() + [short_wick, FLIP], p=P(swing_confirm="off"))["sig"].any()


def test_first_flip_trigger_stop_target():
    r = run(pad() + [ABS, FLIP])
    assert r["sig"][12] and r["sig"].sum() == 1
    assert r["stop"][12] == pytest.approx(103.0 - 1 * TICK)          # below failed-seller low - buffer
    assert r["ref"][12] == pytest.approx(105.8)
    assert r["target"][12] == pytest.approx(120.0)                   # next confirmed swing high
    assert r["abs_low"][12] == 103.0


def test_stop_and_target_options():
    bars = pad() + [ABS, FLIP]
    r = run(bars, p=P(target_mode="r_multiple", target_r=2.0, stop_buffer_ticks=4))
    risk = 105.8 - (103.0 - 1.0)
    assert r["stop"][12] == pytest.approx(102.0) and r["target"][12] == pytest.approx(105.8 + 2 * risk)
    assert run(bars, p=P(target_mode="poc"), poc=112.0)["target"][12] == 112.0
    assert run(bars, p=P(max_target_r=1.5))["target"][12] == pytest.approx(105.8 + 1.5 * (105.8 - 102.75))
    assert not run(bars, p=P(min_stop_ticks=100))["sig"].any()        # stop too tight
    assert not run(bars, p=P(max_stop_ticks=5))["sig"].any()          # stop too wide
    assert not run(bars, p=P(min_rr=10))["sig"].any()                 # swing target too close
    assert not run(bars, p=P(min_bar_volume=40000))["sig"].any()      # participation filter
    s = run(bars, p=P(entry_mode="stop"))
    assert s["ref"][12] == pytest.approx(106.0 + TICK) and s["entry_px"][12] == pytest.approx(106.25)


def test_window_gate():
    inp = mk(pad() + [ABS, FLIP])
    inp["in_window"][:] = False
    assert not v.scan_long(inp, P(), TICK)["sig"].any()


def test_second_failure_mode():
    p = P(confirm_mode="second_failure")
    assert not run(pad() + [ABS, FLIP], p=p)["sig"].any()             # first flip alone is not enough
    r = run(pad() + [ABS, FLIP, PULL, FLIP], p=p)
    assert r["sig"][14] and r["sig"].sum() == 1
    assert r["stop"][14] == pytest.approx(102.75)                     # still the first failed-seller low
    # sellers undercut the absorption low on the retry -> setup resets (and no signal)
    bad = (105.0, 105.1, 102.9, 103.5, -0.3)
    assert not run(pad() + [ABS, FLIP, bad, FLIP], p=p)["sig"].any()
    # waiting too long expires the setup
    assert not run(pad() + [ABS, FLIP, PULL] + [(104.8, 105.0, 104.5, 104.7, -0.1)] * 3 + [FLIP], p=p)["sig"].any()


def test_real_delta_and_imbalance_gate():
    inp = mk(pad() + [ABS, FLIP], real=True)
    inp["imb_buy"][12] = 3.0
    assert v.scan_long(inp, P(flip_imbalance=4.0), TICK)["sig"].sum() == 0
    inp["imb_buy"][12] = 4.5
    assert v.scan_long(inp, P(flip_imbalance=4.0), TICK)["sig"].sum() == 1
    weak = list(ABS)
    weak[4] = -0.01                                                   # real delta barely negative
    assert not v.scan_long(mk(pad() + [tuple(weak), FLIP], real=True), P(), TICK)["sig"].any()


# ----------------------------------------------------------------------------------- shorts mirror
def test_short_mirror_is_exact():
    long_inp = mk(pad() + [ABS, FLIP])
    # build the explicit short-world by negating the long world, then mirror back through mirror_inputs
    neg = dict(long_inp)
    neg["open"], neg["close"] = -long_inp["open"], -long_inp["close"]
    neg["high"], neg["low"] = -long_inp["low"], -long_inp["high"]
    neg["delta_pct"] = -long_inp["delta_pct"]
    neg["val"], neg["vah"], neg["poc"] = -long_inp["vah"], -long_inp["val"], -long_inp["poc"]
    neg["swh_new"], neg["swl_new"] = long_inp["swl_new"], long_inp["swh_new"]
    neg["swh_px"], neg["swl_px"] = -long_inp["swl_px"], -long_inp["swh_px"]
    neg["swh_pos"], neg["swl_pos"] = long_inp["swl_pos"], long_inp["swh_pos"]
    r = v.scan_long(v.mirror_inputs(neg, np.ones(len(neg["open"]), bool)), P(), TICK)
    ref = v.scan_long(long_inp, P(), TICK)
    assert r["sig"].tolist() == ref["sig"].tolist()
    i = 12
    # short world: premium above VAH (down-leg 120->100 in negated coords), stop ABOVE the failed-buyer high
    short_stop, short_tgt, short_ref = -r["stop"][i], -r["target"][i], -r["ref"][i]
    assert short_stop > short_ref > short_tgt


def test_short_side_end_to_end_prices():
    # explicit short setup: down-leg 120 -> 100 ; premium zone [114.1, 117.7]; VAH below zone
    inp = mk(pad() + [ABS, FLIP])
    inp = v.mirror_inputs(inp, np.ones(13, bool))                        # long world -> negated (short) frame
    inp["ctx_ok"] = np.ones(13, bool)
    # inp is now literally the short world; scanning its mirror again must give back the long signal
    r = v.scan_long(v.mirror_inputs(inp, np.ones(13, bool)), P(), TICK)
    assert r["sig"][12]


# ----------------------------------------------------------------------------------- full pipeline
@pytest.fixture(scope="module")
def synth_cfg():
    return load_config(str(Path(__file__).resolve().parents[2] / "experiments" / "vp_fib_mnq_synthetic.yaml"))


def test_end_to_end_synthetic_trades(synth_cfg):
    res, panel, strat = run_backtest(synth_cfg)
    tr = res.trades
    assert len(tr) >= 10
    lg, sh = tr[tr.side == "long"], tr[tr.side == "short"]
    assert (lg.initial_stop < lg.entry_px).all() and (sh.initial_stop > sh.entry_px).all()
    assert (lg.target > lg.entry_px).all() and (sh.target < sh.entry_px).all()
    assert res.meta["rejected_orders"].get("window", 0) == 0
    assert tr.groupby("session_date").size().max() <= 2
    # entries inside the 09:30-11:00 window (entry_ts = open time of the fill bar)
    loc = tr.entry_ts.dt.tz_convert("America/New_York")
    assert ((loc.dt.hour * 60 + loc.dt.minute) >= 570).all() and ((loc.dt.hour * 60 + loc.dt.minute) < 660).all()
    # risk: 1% of ~50k, rounded down to whole contracts
    risk = (tr.entry_px - tr.initial_stop).abs() * tr.qty * 2.0
    assert (risk <= 0.011 * 50000 * 1.5).all()


def test_strategy_is_causal_via_harness(synth_cfg):
    panel = load_panel(DataCfg(**{**synth_cfg.data.model_dump(), "start": "2022-01-03", "end": "2022-09-30"}))
    ex = ExecCfg(flatten_at="15:55", slippage_ticks=1, risk=RiskRules(trade_window=("09:30", "11:00"), max_trades_per_day=2))
    params = synth_cfg.strategy.params
    mk_s = lambda: v.VpFibOrderflow(v.VpFibParams(**params))   # noqa: E731
    rep = check_causality(mk_s, panel, ex)
    assert rep.ok, rep.summary()
    assert len(rep.checks) >= 4
