"""Hand-computed event-engine cases. MNQ: tick 0.25, $2/point. Bars are 5m, first bar ends 09:35 ET."""

import numpy as np
import pytest
from helpers import Scripted, ex, intraday_panel

from tradelab.engine import run_event
from tradelab.strategy import Order

CAP = 100_000.0


def run(bars, script, **exkw):
    p = intraday_panel(bars)
    s = Scripted(script)
    r = run_event(p, s, ex(**exkw), CAP)
    return r, s


def test_long_target_with_commission_and_slippage():
    bars = [(100, 101, 99, 100), (100.5, 102, 100, 101.5), (101.5, 104.25, 101, 104), (104, 104, 103, 103.5)]
    r, _ = run(bars, {0: Order("buy", qty=2, stop=98, target=104)}, commission_per_contract=1.0, slippage_ticks=1)
    t = r.trades.iloc[0]
    assert t.entry_px == 100.5 and t.exit_px == 104 and t.exit_reason == "target"
    assert t.gross_pnl == pytest.approx((104 - 100.5) * 2 * 2)             # 14.0
    # commission 1*2 per side*2 sides = 4 ; slippage entry 1 tick = .25*2*2 = 1.0 ; target is a limit => 0
    assert t.commission == pytest.approx(4.0) and t.slippage_cost == pytest.approx(1.0)
    assert t.costs == pytest.approx(5.0) and t.net_pnl == pytest.approx(9.0)
    assert t.R_gross == pytest.approx(14 / ((100.5 - 98) * 2 * 2)) and t.R_net == pytest.approx(9 / 10)
    assert t.bars_held == 2
    assert r.equity.iloc[-1] == pytest.approx(CAP + 9.0)
    assert r.costs_daily.sum() == pytest.approx(5.0)


def test_short_stop_loss_pnl_and_extra_stop_slippage():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 102.5, 99.75, 102)]
    r, _ = run(bars, {0: Order("sell", qty=1, stop=102, target=95)}, commission_per_contract=0.5,
               slippage_ticks=1, stop_extra_slippage_ticks=1)
    t = r.trades.iloc[0]
    assert t.side == "short" and t.entry_px == 100 and t.exit_px == 102 and t.exit_reason == "stop"
    assert t.gross_pnl == pytest.approx(-2 * 2)                 # -4
    # comm 0.5*2 = 1 ; slippage: entry 1 tick (0.5) + stop 2 ticks (1.0)
    assert t.costs == pytest.approx(1.0 + 0.5 + 1.0)
    assert t.net_pnl == pytest.approx(-4 - 2.5) and t.R_gross == pytest.approx(-1.0)


def test_stop_and_target_same_bar_is_stop_conservative_and_target_optimistic():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 106, 96, 100)]
    script = {0: Order("buy", qty=1, stop=97, target=105)}
    r, _ = run(bars, script)
    assert r.trades.iloc[0].exit_reason == "stop" and r.trades.iloc[0].exit_px == 97
    r, _ = run(bars, script, intrabar="optimistic")
    assert r.trades.iloc[0].exit_reason == "target" and r.trades.iloc[0].exit_px == 105


def test_gap_through_stop_fills_at_open_and_gap_through_target_at_open():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (95, 96, 94, 95.5)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=98, target=110)})
    t = r.trades.iloc[0]
    assert t.exit_px == 95 and t.exit_reason == "stop" and t.gross_pnl == pytest.approx(-5 * 2)
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (112, 113, 111, 112)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=98, target=110)})
    assert r.trades.iloc[0].exit_px == 112 and r.trades.iloc[0].exit_reason == "target"


def test_entry_bar_also_checks_stop():
    bars = [(100, 101, 99, 100), (100, 100.5, 96, 97), (97, 98, 96, 97)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=98)})
    t = r.trades.iloc[0]
    assert t.entry_px == 100 and t.exit_px == 98 and t.bars_held == 1


def test_time_stop_exits_at_close_of_nth_bar():
    bars = [(100, 101, 99, 100)] + [(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(1, 6)]
    r, _ = run(bars, {0: Order("buy", qty=1, time_stop_bars=3)})
    t = r.trades.iloc[0]
    # entry open of bar1 (=101); bars held 1 (bar1), 2 (bar2), 3 (bar3) -> exit at close of bar 3 = 103.5
    assert t.entry_px == 101 and t.exit_px == 103.5 and t.exit_reason == "time_stop" and t.bars_held == 3


def test_flatten_at_and_session_end():
    bars = [(100, 101, 99, 100 + i * 0.25) for i in range(8)]   # ends 09:35 ... 10:10
    r, _ = run(bars, {0: Order("buy", qty=1)}, flatten_at="09:50")
    t = r.trades.iloc[0]
    assert t.exit_reason == "flatten_at" and t.exit_ts.tz_convert("America/New_York").strftime("%H:%M") == "09:50"
    assert t.exit_px == bars[3][3]
    # session end is the SCHEDULED close (16:00): data that stops at 10:10 simply ends
    r, _ = run(bars, {0: Order("buy", qty=1)})
    t = r.trades.iloc[0]
    assert t.exit_reason == "end_of_data" and t.exit_px == bars[-1][3]
    # full all-session day on a Globex instrument: 90 bars end 09:35..17:00 -> session_end at the 17:00 bar close
    full = [(100, 101, 99, 100 + (i % 3) * 0.25) for i in range(90)] + [(100, 101, 99, 100)] * 3
    r, _ = run(full, {0: Order("buy", qty=1)})
    t = r.trades.iloc[0]
    assert t.exit_reason == "session_end" and t.exit_ts.tz_convert("America/New_York").strftime("%H:%M") == "17:00"


def test_limit_entry_gap_and_stop_entry_gap():
    bars = [(100, 101, 99, 100), (99, 99.5, 97, 98), (98, 99, 97.5, 98.5)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="limit", price=98.0, valid_bars=2)})
    assert r.trades.iloc[0].entry_px == 98.0           # touched intrabar -> limit price
    bars = [(100, 101, 99, 100), (97, 98, 96, 97), (97, 98, 96, 97)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="limit", price=98.0, valid_bars=2)})
    assert r.trades.iloc[0].entry_px == 97.0           # gapped through limit -> fill at open (better)
    bars = [(100, 101, 99, 100), (103, 104, 102, 103), (103, 104, 102, 103)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="stop", price=101.0, valid_bars=2)})
    assert r.trades.iloc[0].entry_px == 103.0          # gapped through buy-stop -> fill at open (worse)


def test_limit_order_expires():
    bars = [(100, 101, 99, 100), (100, 101, 99.5, 100), (100, 101, 99.5, 100), (100, 101, 90, 95)]
    r, _ = run(bars, {0: Order("buy", qty=1, entry="limit", price=98.0, valid_bars=2)})
    assert len(r.trades) == 0 and r.meta["rejected_orders"].get("expired") == 1


def test_stop_after_two_consecutive_losses_and_max_trades_per_day():
    # each cycle: buy at open, stopped out on the same bar
    bars = [(100, 101, 99, 100)] + [(100, 100.5, 97, 100)] * 9
    script = lambda ctx: Order("buy", qty=1, stop=99) if ctx.position == 0 else None
    r, s = run(bars, {i: script for i in range(9)}, risk={"stop_after_consecutive_losses": 2})
    assert len(r.trades) == 2 and r.meta["rejected_orders"]["consecutive_losses"] > 0
    r, _ = run(bars, {i: script for i in range(9)}, risk={"max_trades_per_day": 3})
    assert len(r.trades) == 3
    r, _ = run(bars, {i: script for i in range(9)})
    assert len(r.trades) == 9


def test_win_resets_consecutive_losses():
    bars = [(100, 101, 99, 100),
            (100, 100.5, 97, 100),     # loss
            (100, 102, 99.5, 101),     # win (target 101)
            (100, 100.5, 97, 100),     # loss
            (100, 100.5, 97, 100),     # loss -> third trade? allowed because streak reset by the win
            (100, 100.5, 97, 100), (100, 100.5, 97, 100)]
    def mk(ctx):
        if ctx.position != 0:
            return None
        win_bar = ctx.i == 1
        return Order("buy", qty=1, stop=99, target=101 if win_bar else 120)
    r, _ = run(bars, {i: mk for i in range(6)}, risk={"stop_after_consecutive_losses": 2})
    assert list(np.sign(r.trades.net_pnl)) == [-1, 1, -1, -1]


def test_trade_window_and_min_volume_filter():
    bars = [(100, 101, 99, 100, 500)] * 3 + [(100, 101, 99, 100, 5000)] * 3
    # decisions at every bar; window only allows fills with bar start in [09:45, 09:55)
    s = {i: Order("buy", qty=1, stop=50, target=120) for i in (0, 2, 3)}
    r, _ = run(bars, s, risk={"trade_window": ("09:45", "09:55")})
    assert len(r.trades) == 1 and r.trades.iloc[0].entry_ts.tz_convert("America/New_York").strftime("%H:%M") == "09:45"
    r, _ = run(bars, {2: Order("buy", qty=1, stop=50), 3: Order("buy", qty=1, stop=50)}, risk={"min_decision_bar_volume": 1000})
    assert r.meta["rejected_orders"].get("min_volume") == 1 and len(r.trades) == 1


def test_daily_loss_limit_usd():
    bars = [(100, 101, 99, 100)] + [(100, 100.5, 96, 100)] * 8
    script = lambda ctx: Order("buy", qty=1, stop=98) if ctx.position == 0 else None
    r, _ = run(bars, {i: script for i in range(8)}, risk={"daily_loss_limit_usd": 6.0})
    assert len(r.trades) == 2           # -4, -4 -> limit reached after second


def test_tick_rounding_of_stop_target_and_limit():
    bars = [(100, 101, 99, 100), (100, 100.2, 99.9, 100), (100, 101, 99.9, 100)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=97.9, target=104.13)})
    t = r.trades.iloc[0]
    assert t.initial_stop == 97.75 and t.target == 104.25            # adverse rounding: long stop down, target up
    assert (t.initial_stop / 0.25) == pytest.approx(round(t.initial_stop / 0.25))


def test_risk_pct_sizing_floor():
    bars = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)]
    r, _ = run(bars, {0: Order("buy", risk_pct=0.01, stop=97.5)})
    # risk$ 1000 / (2.5 pts * $2) = 200 contracts
    assert r.trades.iloc[0].qty == 200
    r, _ = run(bars, {0: Order("buy", risk_pct=0.01, stop=100 - 400)})   # too wide -> 1000/(400*2)=1.25 -> 1
    assert r.trades.iloc[0].qty == 1


def test_modify_flatten_and_reversal():
    bars = [(100, 101, 99, 100), (100, 101, 99.5, 100.5), (101, 102, 100.5, 101.5), (102, 103, 101, 102), (103, 104, 102, 103)]
    def f1(ctx): return Order.modify(stop=100.75)
    r, _ = run(bars, {0: Order("buy", qty=1, stop=90), 1: f1})
    t = r.trades.iloc[0]
    assert t.exit_reason == "stop" and t.exit_px == 100.75 and t.initial_stop == 90
    # reversal: flatten + sell in the same decision
    r, _ = run(bars, {0: Order("buy", qty=1), 2: [Order.flatten(), Order("sell", qty=2, tag="rev")]})
    assert list(r.trades.side) == ["long", "short"] and r.trades.iloc[0].exit_px == 102 and r.trades.iloc[1].entry_px == 102
    assert r.trades.iloc[1].qty == 2


def test_trailing_stop_ratchets():
    bars = [(100, 101, 99, 100), (100, 103, 100, 102.5), (102.5, 108, 102, 107), (107, 107.5, 104, 105)]
    r, _ = run(bars, {0: Order("buy", qty=1, stop=97, trailing=3)})
    t = r.trades.iloc[0]
    # after bar1: ext 103 -> stop 100 ; after bar2: ext 108 -> stop 105 ; bar3 low 104 <= 105 -> exit 105
    assert t.exit_px == 105 and t.exit_reason == "trailing"


def test_equity_mark_to_market_and_positions():
    bars = [(100, 101, 99, 100), (100, 102, 99.5, 101), (101, 103, 100.5, 102), (102, 102.5, 101, 101.5)]
    r, _ = run(bars, {0: Order("buy", qty=3)}, commission_per_contract=0.0)
    # entry 100 (open bar1); closes 101,102 -> unrealized 3*2*(c-100)
    assert r.equity.iloc[1] == pytest.approx(CAP + 3 * 2 * 1.0)
    assert r.equity.iloc[2] == pytest.approx(CAP + 3 * 2 * 2.0)
    assert list(r.positions.iloc[:, 0]) == [0, 3, 3, 0]            # session_end at last bar
    assert r.returns_daily.iloc[0] == pytest.approx(r.equity.iloc[-1] / CAP - 1)


def test_on_fill_called_causally_after_the_fill_bar():
    bars = [(100, 101, 99, 100), (100, 101, 99.5, 100.5), (100.5, 101, 99, 100)]
    r, s = run(bars, {0: Order("buy", qty=1)})
    assert [f.reason for f in s.fills][:1] == ["entry"]


def test_runresult_contract_fields_and_empty_trades_columns():
    from tradelab.engine import TRADE_COLUMNS, RunResult
    import dataclasses
    assert [f.name for f in dataclasses.fields(RunResult)] == [
        "equity", "returns_daily", "positions", "trades", "costs_daily", "benchmark_daily", "rf_daily",
        "initial_capital", "meta"]
    assert RunResult.__dataclass_params__.frozen
    r, _ = run([(100, 101, 99, 100)] * 3, {})
    assert list(r.trades.columns) == TRADE_COLUMNS and len(r.trades) == 0
    assert r.equity.index.tz is not None and str(r.equity.index.tz) == "UTC"
    assert r.returns_daily.index.tz is None


def test_point_values_mes_vs_mnq():
    bars = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 104.5, 99, 104)]
    p = intraday_panel(bars, symbol="MES")
    r = run_event(p, Scripted({0: Order("buy", qty=1, target=104)}), ex(), CAP)
    assert r.trades.iloc[0].gross_pnl == pytest.approx(4 * 5)       # MES $5/pt
