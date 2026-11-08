"""Regression tests for the correctness review (event engine). MNQ: tick 0.25, $2/pt; 5m bars, first ends 09:35 ET."""
import pandas as pd
import pytest
from helpers import ET, Scripted, ex, intraday_panel

from tradelab.engine import run_event
from tradelab.strategy import Order

CAP = 100_000.0


def run(bars, script, *, start="2024-01-02 09:35", **exkw):
    p = intraday_panel(bars, start=start)
    s = Scripted(script)
    return run_event(p, s, ex(**exkw), CAP), s


# ---- 3. limit entry filled mid-bar must not collect a target that traded before the fill
LIMIT_BARS = [(100, 100.5, 99.5, 100), (105, 110, 100, 102), (102, 102.5, 101.5, 102), (102, 102.5, 101.5, 102), (102, 102.5, 101.5, 102)]


def test_limit_entry_fill_bar_target_is_not_taken_conservative():
    o = Order("buy", qty=1, entry="limit", price=101, stop=95, target=108, valid_bars=2)
    r, _ = run(LIMIT_BARS, {0: o})
    t = r.trades.iloc[0]
    assert t.entry_px == 101 and t.exit_reason != "target" and t.exit_px != 108
    assert t.MFE_usd == pytest.approx((102.5 - 101) * 2)       # fill-bar high (110) happened before the fill: not counted
    assert t.MAE_usd == pytest.approx((101 - 100) * 2)         # fill-bar low counts (worst case)
    r, _ = run(LIMIT_BARS, {0: o}, intrabar="optimistic")
    assert r.trades.iloc[0].exit_reason == "target" and r.trades.iloc[0].exit_px == 108


def test_limit_entry_fill_bar_still_checks_stop():
    bars = [(100, 100.5, 99.5, 100), (105, 110, 94, 102), (102, 102.5, 101.5, 102)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="limit", price=101, stop=95, target=108, valid_bars=2)})
    t = r.trades.iloc[0]
    assert t.exit_reason == "stop" and t.exit_px == 95


def test_stop_entry_target_after_trigger_is_legitimate():
    bars = [(100, 100.5, 99.5, 100), (100, 107, 99, 105), (105, 105.5, 104.5, 105)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="stop", price=103, stop=95, target=106, valid_bars=2)})
    t = r.trades.iloc[0]
    assert t.entry_px == 103 and t.exit_reason == "target" and t.exit_px == 106


# ---- 4. market entry gapping through its stop
def test_market_entry_gapped_through_stop_is_filled_and_stopped_at_open():
    bars = [(100, 100, 100, 100), (98, 98.5, 97.5, 98), (98, 99, 97, 98)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=99, target=105)}, commission_per_contract=1.0, slippage_ticks=1,
               stop_extra_slippage_ticks=1)
    assert len(r.trades) == 1 and not r.meta["rejected_orders"].get("bad_stop")
    t = r.trades.iloc[0]
    assert t.entry_px == 98 and t.exit_px == 98 and t.exit_reason == "stop"
    # costs: 2 sides commission (2.0) + entry 1 tick (0.5) + stop 2 ticks (1.0)
    assert t.costs == pytest.approx(2.0 + 0.5 + 1.0) and t.net_pnl == pytest.approx(-3.5)
    assert r.equity.iloc[-1] == pytest.approx(CAP - 3.5)


def test_gapped_stop_risk_sizing_uses_decision_close_distance():
    bars = [(100, 100, 100, 100), (98, 98.5, 97.5, 98), (98, 99, 97, 98)]
    r, _ = run(bars, {0: Order("buy", risk_pct=0.001, stop=99)})
    # risk$ 100 / (|100-99| * 2) = 50 contracts (NOT 100/(|98-99|*2) from the post-gap price distance, nor infinity)
    assert r.trades.iloc[0].qty == 50


def test_market_entry_with_stop_on_wrong_side_of_decision_close_is_rejected():
    bars = [(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=101)})
    assert len(r.trades) == 0 and r.meta["rejected_orders"].get("bad_stop") == 1


# ---- 6. flatten_at must not hit the Globex evening
def test_flatten_at_does_not_fire_on_globex_evening_bars():
    bars = [(100, 101, 99, 100)] * 12
    r, _ = run(bars, {0: Order("buy", qty=1)}, start="2024-03-04 18:05", flatten_at="15:55", session_flat=False)
    t = r.trades.iloc[0]
    assert t.exit_reason == "end_of_data" and t.bars_held == 11


def test_flatten_at_fires_next_afternoon_for_evening_entry():
    n = 24 * 12 - 6
    bars = [(100, 101, 99, 100)] * n
    r, _ = run(bars, {0: Order("buy", qty=1)}, start="2024-03-04 18:05", flatten_at="15:55", session_flat=False)
    t = r.trades.iloc[0]
    assert t.exit_reason == "flatten_at"
    assert t.exit_ts.tz_convert(ET).strftime("%Y-%m-%d %H:%M") == "2024-03-05 15:55"


# ---- adverse tick rounding of order prices
def test_tick_rounding_is_adverse_for_stops_targets_and_limits():
    bars = [(100, 100.2, 99.9, 100), (100, 100.2, 99.9, 100), (100, 101, 99.9, 100)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=97.9, target=104.01)})
    t = r.trades.iloc[0]
    assert t.initial_stop == 97.75 and t.target == 104.25            # long: stop down, target up
    r, _ = run(bars, {0: Order("sell", qty=1, stop=102.1, target=95.9)})
    t = r.trades.iloc[0]
    assert t.initial_stop == 102.25 and t.target == 95.75            # short: stop up, target down
    wide = [(100, 100.5, 99.5, 100), (100, 100.5, 97.5, 99), (99, 99, 99, 99)]
    r, _ = run(wide, {0: Order("buy", qty=1, entry="limit", price=98.1, valid_bars=1)})
    assert r.trades.iloc[0].entry_px == 98.0                          # buy limit rounds down
    wide = [(100, 100.5, 99.5, 100), (100, 102.5, 99.5, 99), (99, 99, 99, 99)]
    r, _ = run(wide, {0: Order("sell", qty=1, entry="limit", price=101.9, valid_bars=1)})
    assert r.trades.iloc[0].entry_px == 102.0                         # sell limit rounds up


# ---- limit_fill touch | through
def test_limit_entry_needs_trade_through_by_default():
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 98.0, 99), (99, 99.5, 98.5, 99), (99, 99.5, 98.5, 99)]
    o = Order("buy", qty=1, entry="limit", price=98.0, valid_bars=1)
    r, _ = run(bars, {0: o})
    assert len(r.trades) == 0 and r.meta["rejected_orders"].get("expired") == 1        # touched, not traded through
    r, _ = run(bars, {0: o}, limit_fill="touch")
    assert r.trades.iloc[0].entry_px == 98.0
    bars[1] = (100, 100.5, 97.75, 99)                                               # one tick through
    r, _ = run(bars, {0: o})
    assert r.trades.iloc[0].entry_px == 98.0


def test_target_needs_trade_through_by_default():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 104, 100, 103), (103, 103.5, 102, 103)]
    o = Order("buy", qty=1, stop=90, target=104)
    r, _ = run(bars, {0: o})
    assert r.trades.iloc[0].exit_reason != "target"
    r, _ = run(bars, {0: o}, limit_fill="touch")
    assert r.trades.iloc[0].exit_reason == "target" and r.trades.iloc[0].exit_px == 104
    bars[2] = (100, 104.25, 100, 103)
    r, _ = run(bars, {0: o})
    assert r.trades.iloc[0].exit_reason == "target"


# ---- trailing label only for a genuinely trailed stop
def test_modified_stop_is_not_labelled_trailing_even_when_trail_is_set():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100.2), (100.2, 100.4, 99.6, 100), (100, 100.2, 99.0, 99.5), (99.5, 99.7, 99.0, 99.5)]
    script = {0: Order("buy", qty=1, stop=95, trailing=50), 1: Order.modify(stop=99.75)}
    r, _ = run(bars, script)
    t = r.trades.iloc[0]
    assert t.exit_px == 99.75 and t.exit_reason == "stop"


def test_trailing_label_kept_for_ratcheted_stop():
    bars = [(100, 101, 99, 100), (100, 103, 100, 102.5), (102.5, 108, 102, 107), (107, 107.5, 104, 105)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=97, trailing=3)})
    assert r.trades.iloc[0].exit_reason == "trailing"
    bars = [(100, 101, 99, 100), (100, 100.5, 98, 99)]
    r, _ = run(bars + [(99, 99.5, 96, 97)], {0: Order("buy", qty=1, stop=97.5, trailing=50)})
    assert r.trades.iloc[0].exit_reason == "stop"          # trail never improved the initial stop


# ---- a position surviving its session (scheduled close bar missing) is closed at the next session open
def test_position_surviving_session_is_closed_at_next_open():
    d1 = intraday_panel([(100, 101, 99, 100)] * 6, start="2024-01-02 09:35")["MNQ"]          # data stops at 10:00
    d2 = intraday_panel([(110, 111, 109, 110)] * 4, start="2024-01-03 09:35")["MNQ"]
    from tradelab.data.panel import Panel
    from tradelab.data.sessions import tag_sessions
    bars = tag_sessions(pd.concat([d1, d2])[["open", "high", "low", "close", "volume"]], intraday_panel([(1, 1, 1, 1)]).specs["MNQ"], "5m")
    p = Panel({"MNQ": bars}, "5m", intraday_panel([(1, 1, 1, 1)]).specs)
    assert not bars["is_session_last"].any()
    r = run_event(p, Scripted({0: Order("buy", qty=1)}), ex(), CAP)
    t = r.trades.iloc[0]
    assert t.exit_reason == "session_end" and t.exit_px == 110
    assert t.exit_ts.tz_convert(ET).strftime("%Y-%m-%d %H:%M") == "2024-01-03 09:30"
