"""Event-driven engine (one instrument, one net position). See docs/EXECUTION_MODEL.md.

Timeline for bar j (bar-end stamps; decisions are taken at the CLOSE of a bar):
  1. orders emitted at the close of j-1 are processed: flatten, modify, market entries (fill at open_j),
     limit/stop entries start working;
  2. working entries are matched against bar j;
  3. the open position's stop/target bracket is checked against bar j (gap rules, intrabar policy);
  4. scheduled exits at the close of j: time stop, flatten_at, session end, end of data;
  5. trailing stop ratchets with bar j's extreme (effective from j+1);
  6. fills of bar j are delivered via on_fill, then on_bar(ctx) decides orders for j+1.
Only arrays of prepared features at index <= j are reachable from the context.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd

from ..config.schema import ExecCfg
from ..data.calendar import hhmm_to_minutes, is_daily
from ..data.panel import Panel
from ..strategy.base import Fill, Order, Strategy, features_to_arrays
from ..strategy.ctx import BarContext
from .costs import CostModel
from .fills import resolve_bracket, resolve_entry, round_tick
from .result import TRADE_COLUMNS, RunResult, daily_from_equity, daily_sum, empty_trades


class _S:
    __slots__ = ("pos", "entry_px", "entry_j", "stop", "target", "init_stop", "trail", "trail_ext", "tstop",
                 "tag", "entry_comm", "entry_slip", "mae", "mfe", "bars", "entry_ts", "risk_usd", "side", "risk_pts",
                 "trail_stop", "partial")

    def __init__(self):
        self.pos = 0.0


def _order_key(od: Order) -> tuple:
    def f(x):
        return None if x is None or (isinstance(x, float) and x != x) else (round(float(x), 8) if isinstance(x, (int, float)) else x)
    return (od.kind, od.side, f(od.qty), f(od.risk_pct), od.entry, f(od.price), f(od.stop), f(od.target), f(od.trailing),
            od.time_stop_bars, od.valid_bars, od.tag)


def _freq_minutes(freq: str) -> float | None:
    if is_daily(freq):
        return None
    from ..data.calendar import freq_to_timedelta

    return freq_to_timedelta(freq).total_seconds() / 60.0


def run_event(panel: Panel, strategy: Strategy, ex: ExecCfg, capital: float, *, cost_mult: float = 1.0,
              meta: dict | None = None, feats=None, order_log: list | None = None) -> RunResult:
    sym = panel.primary
    b = panel[sym]
    spec = panel.specs[sym]
    n = len(b)
    idx = b.index
    cm = CostModel.from_cfg(ex, spec, cost_mult)
    tick, pv = spec.tick_size, spec.point_value
    daily = is_daily(panel.freq)
    bar_min = _freq_minutes(panel.freq)
    o_, h_, l_, c_, v_ = (b[k].to_numpy(float).tolist() for k in ("open", "high", "low", "close", "volume"))
    bid_ = b["bid_vol"].to_numpy(float).tolist() if "bid_vol" in b else None
    ask_ = b["ask_vol"].to_numpy(float).tolist() if "ask_vol" in b else None
    sdates = b["session_date"].to_numpy()
    codes = pd.factorize(sdates)[0].tolist()
    stype = b["session_type"].tolist()
    biss = b["bar_in_session"].tolist()
    is_last = b["is_session_last"].tolist()
    loc = idx.tz_convert(spec.tz)
    end_min = (loc.hour * 60 + loc.minute).to_numpy().tolist()
    # exchange-session clock: Globex evening bars (end after 18:00 ET) belong to the NEXT session date, so they sit
    # "before midnight" of that session (negative minutes). flatten_at is compared on this clock.
    if spec.session == "globex":
        sess_min = [m - 1440 if m > 18 * 60 else m for m in end_min]
    else:
        sess_min = end_min
    through = ex.limit_fill == "through"

    if feats is None:
        feats = features_to_arrays(strategy.prepare(panel), idx)
    active = feats.get("_active")
    active = active.astype(bool).tolist() if active is not None else None

    rk = ex.risk
    w_lo = w_hi = None
    if rk.trade_window and not daily:
        w_lo, w_hi = hhmm_to_minutes(rk.trade_window[0]), hhmm_to_minutes(rk.trade_window[1])
    fl_min = hhmm_to_minutes(ex.flatten_at) if (ex.flatten_at and not daily) else None
    sess_flat = ex.session_flat and not daily
    max_tr, max_cl = rk.max_trades_per_day, rk.stop_after_consecutive_losses
    dl_usd, dl_r, min_vol = rk.daily_loss_limit_usd, rk.daily_loss_limit_r, rk.min_decision_bar_volume
    intrabar = ex.intrabar

    # ---- output buffers (event-sparse writes)
    pos_arr = np.zeros(n)
    entry_arr = np.zeros(n)
    real_inc = np.zeros(n)
    cost_arr = np.zeros(n)
    trades: list[dict] = []
    rejects: Counter = Counter()

    S = _S()
    S.pos = 0.0
    real_cum = 0.0
    cur_code = -1
    sess = {"pnl": 0.0, "r": 0.0, "trades": 0, "cl": 0}
    pend_flat = None           # tag
    pend_mod: list[Order] = []
    pend_entries: list[tuple] = []   # (order, dec_code, dec_vol, dec_close)
    working: list[list] = []         # [order, expire_j, dec_code, dec_vol]
    fills_bar: list[Fill] = []

    ctx = BarContext(feats, spec, sym, idx, spec.tz)
    on_bar, on_fill = strategy.on_bar, strategy.on_fill

    def size(order: Order, px: float, stop: float | None):
        if order.qty:
            q = abs(order.qty)
        elif order.risk_pct:
            if stop is None:
                return 0.0
            rp = abs(px - stop)
            if rp <= 0:
                return 0.0
            q = (capital + real_cum) * order.risk_pct / (rp * pv)
        else:
            q = 1.0
        if spec.integer_qty:
            q = float(math.floor(q + 1e-9))
        return q

    bar_td = pd.Timedelta(minutes=bar_min) if bar_min else None

    def open_ts(j: int):
        """Time of the open of bar j (= decision-bar end when contiguous)."""
        if bar_td is not None:
            return idx[j] - bar_td
        return idx[j - 1] if j > 0 else idx[j]

    def stop_mode(d: int) -> str:      # adverse rounding of a protective stop: long sells lower, short buys higher
        return "down" if d > 0 else "up"

    def target_mode(d: int) -> str:    # adverse rounding of a limit target: long sells higher, short buys lower
        return "up" if d > 0 else "down"

    def do_exit(j: int, px: float, reason: str, is_stop: bool, at_open: bool = False):
        nonlocal real_cum
        q = abs(S.pos)
        d = 1 if S.pos > 0 else -1
        px = round_tick(px, tick)
        gross = (px - S.entry_px) * d * q * pv
        ecomm = cm.commission(q, px)
        eslip = 0.0 if reason == "target" else cm.slippage(q, px, is_stop)
        comm = S.entry_comm + ecomm
        slip = S.entry_slip + eslip
        costs = comm + slip
        net = gross - costs
        risk_usd = S.risk_usd
        mae_usd = S.mae * q * pv
        mfe_usd = S.mfe * q * pv
        ip = S.risk_pts if S.init_stop is not None else float("nan")
        trades.append({
            "id": len(trades) + 1, "symbol": sym, "side": "long" if d > 0 else "short", "qty": q,
            "entry_ts": S.entry_ts, "entry_px": S.entry_px, "exit_ts": open_ts(j) if at_open else idx[j], "exit_px": px, "exit_reason": reason,
            "initial_stop": S.init_stop, "target": S.target if S.target is not None else float("nan"),
            "R_gross": gross / risk_usd if risk_usd else float("nan"),
            "R_net": net / risk_usd if risk_usd else float("nan"),
            "MAE_R": S.mae / ip if ip == ip and ip > 0 else float("nan"),
            "MFE_R": S.mfe / ip if ip == ip and ip > 0 else float("nan"),
            "MAE_usd": mae_usd, "MFE_usd": mfe_usd, "bars_held": S.bars,
            "session_date": sdates[S.entry_j], "tag": S.tag, "gross_pnl": gross, "costs": costs, "net_pnl": net,
            "commission": comm, "slippage_cost": slip,
        })
        real_inc[j] += gross - ecomm - eslip
        real_cum += gross - ecomm - eslip
        cost_arr[j] += ecomm + eslip
        sess["pnl"] += net
        if risk_usd:
            sess["r"] += net / risk_usd
        if net < 0:
            sess["cl"] += 1
        elif net > 0:
            sess["cl"] = 0
        fills_bar.append(Fill(idx[j], "sell" if d > 0 else "buy", q, px, reason, S.tag, False, net))
        S.pos = 0.0

    def try_entry(j: int, order: Order, fill_px: float, is_stop: bool, dec_code: int, dec_vol: float,
                  dec_close: float | None = None) -> bool:
        nonlocal real_cum
        if S.pos != 0:
            rejects["in_position"] += 1
            return False
        if sess_flat and dec_code != codes[j]:
            rejects["cross_session"] += 1
            return False
        if w_lo is not None:
            sm = end_min[j] - (bar_min or 0)
            if not (w_lo <= sm < w_hi):
                rejects["window"] += 1
                return False
        if max_tr is not None and sess["trades"] >= max_tr:
            rejects["max_trades"] += 1
            return False
        if max_cl is not None and sess["cl"] >= max_cl:
            rejects["consecutive_losses"] += 1
            return False
        if dl_usd is not None and sess["pnl"] <= -dl_usd:
            rejects["daily_loss_usd"] += 1
            return False
        if dl_r is not None and sess["r"] <= -dl_r:
            rejects["daily_loss_r"] += 1
            return False
        if min_vol is not None and dec_vol < min_vol:
            rejects["min_volume"] += 1
            return False
        px = round_tick(fill_px, tick)
        d = order.sign
        stop = round_tick(order.stop, tick, stop_mode(d)) if order.stop is not None else None
        tgt = round_tick(order.target, tick, target_mode(d)) if order.target is not None else None
        gapped = False
        risk_ref = px
        if stop is not None and ((d > 0 and stop >= px) or (d < 0 and stop <= px)):
            # stop already on the wrong side of the FILL. A market entry whose open gapped through a stop that was valid
            # at the decision close is a real (bad) outcome: fill at the open and stop out at once. Anything else is
            # an invalid order.
            if (order.entry == "market" and dec_close is not None
                    and not ((d > 0 and stop >= dec_close) or (d < 0 and stop <= dec_close))):
                gapped = True
                risk_ref = dec_close          # size on the risk the strategy planned, not on the post-gap distance
            else:
                rejects["bad_stop"] += 1
                return False
        elif (stop is not None and order.entry == "market" and dec_close is not None
              and ((d > 0 and stop >= dec_close) or (d < 0 and stop <= dec_close))):
            rejects["bad_stop"] += 1          # stop on the wrong side of the decision close
            return False
        q = size(order, risk_ref, stop)
        if q <= 0:
            rejects["size_zero"] += 1
            return False
        S.pos = d * q
        S.side = d
        S.entry_px, S.entry_j, S.entry_ts = px, j, open_ts(j)
        S.stop, S.init_stop, S.target = stop, stop, tgt
        S.trail = order.trailing
        S.trail_ext = px
        S.tstop = order.time_stop_bars
        S.tag = order.tag
        S.bars = 0
        S.mae = S.mfe = 0.0
        S.risk_pts = abs(risk_ref - stop) if stop is not None else 0.0
        S.risk_usd = S.risk_pts * q * pv
        S.trail_stop = False
        S.partial = False
        S.entry_comm = cm.commission(q, px)
        S.entry_slip = cm.slippage(q, px, is_stop)
        real_inc[j] -= S.entry_comm + S.entry_slip
        real_cum -= S.entry_comm + S.entry_slip
        cost_arr[j] += S.entry_comm + S.entry_slip
        sess["trades"] += 1
        fills_bar.append(Fill(idx[j], order.side, q, px, "entry", order.tag, True))
        if gapped:
            do_exit(j, px, "stop", True, True)
        return True

    for j in range(n):
        oj, hj, lj, cj = o_[j], h_[j], l_[j], c_[j]
        if codes[j] != cur_code:
            cur_code = codes[j]
            sess["pnl"] = 0.0
            sess["r"] = 0.0
            sess["trades"] = 0
            sess["cl"] = 0
            # unfilled working orders do not survive a session when session_flat
            if sess_flat:
                working = [w for w in working if w[2] == cur_code]
        fills_bar.clear()

        # -- 0. a position that survived its session (scheduled close bar missing from the data, e.g. early close):
        #       it is closed at the first open of the next session
        if sess_flat and S.pos != 0 and j > 0 and codes[j] != codes[j - 1]:
            do_exit(j, oj, "session_end", False, True)
        # -- 1. pending actions from the previous close
        if pend_flat is not None:
            if S.pos != 0:
                do_exit(j, oj, "flatten", False, True)
            pend_flat = None
        if pend_mod:
            if S.pos != 0:
                dd = 1 if S.pos > 0 else -1
                for m in pend_mod:
                    if m.stop is not None:
                        S.stop = round_tick(m.stop, tick, stop_mode(dd))
                        S.trail_stop = False
                    if m.target is not None:
                        S.target = round_tick(m.target, tick, target_mode(dd))
            pend_mod = []
        held_at_open = S.pos != 0
        if pend_entries:
            for (od, dc, dv, dcl) in pend_entries:
                if od.entry == "market":
                    if S.pos == 0:
                        try_entry(j, od, oj, False, dc, dv, dcl)
                    else:
                        rejects["in_position"] += 1
                else:
                    working.append([od, j + max(1, od.valid_bars) - 1, dc, dv])
            pend_entries = []
        # -- 2. working limit/stop entries
        if working:
            keep = []
            for w in working:
                od = w[0]
                if j > w[1]:
                    rejects["expired"] += 1
                    continue
                if S.pos != 0:
                    keep.append(w)
                    continue
                r = resolve_entry(od.sign, od.entry, od.price, oj, hj, lj, tick=tick, through=through)
                if r is None:
                    keep.append(w)
                    continue
                fpx, is_stop = r
                if try_entry(j, od, fpx, is_stop, w[2], w[3]):
                    # a limit order filled inside the bar: the bar's range BEFORE the fill is unknown, so under the
                    # conservative policy only the stop (and MAE) of that bar are credited, never the target / MFE
                    S.partial = intrabar == "conservative" and od.entry == "limit" and fpx != oj
                    # fill at open (gap) behaves as held-at-open for gap rules only if fill == open
                    continue
                # rejected -> dropped
            working = keep
        # entered at bar open by market order => whole bar is post-entry; gap rules do not apply on entry bar
        # -- 3. bracket
        if S.pos != 0:
            S.bars += 1
            d = 1 if S.pos > 0 else -1
            ep = S.entry_px
            fill_bar_partial = S.partial and S.entry_j == j
            if d > 0:
                S.mae = max(S.mae, ep - lj)
                S.mfe = max(S.mfe, (cj if fill_bar_partial else hj) - ep)
            else:
                S.mae = max(S.mae, hj - ep)
                S.mfe = max(S.mfe, ep - (cj if fill_bar_partial else lj))
            if S.stop is not None or S.target is not None:
                r = resolve_bracket(d, oj, hj, lj, S.stop, None if fill_bar_partial else S.target,
                                    held_at_open=held_at_open and S.entry_j != j, intrabar=intrabar, tick=tick,
                                    through=through)
                if r is not None:
                    reason, px = r
                    if reason == "stop" and S.trail_stop:
                        reason = "trailing"
                    do_exit(j, px, reason, reason in ("stop", "trailing"), px == oj and held_at_open and S.entry_j != j)
        # -- 4. scheduled exits at the close of j
        if S.pos != 0:
            reason = None
            if S.tstop is not None and S.bars >= S.tstop:
                reason = "time_stop"
            elif fl_min is not None and sess_min[j] >= fl_min:
                reason = "flatten_at"
            elif sess_flat and is_last[j]:
                reason = "session_end"
            elif j == n - 1:
                reason = "end_of_data"
            if reason:
                do_exit(j, cj, reason, False)
        # -- 5. trail ratchet + record state
        if S.pos != 0:
            if S.trail is not None:
                if S.pos > 0:
                    S.trail_ext = max(S.trail_ext, hj)
                    ns = round_tick(S.trail_ext - S.trail, tick, "down")
                    if S.stop is None or ns > S.stop:
                        S.stop = ns
                        S.trail_stop = True
                else:
                    S.trail_ext = min(S.trail_ext, lj)
                    ns = round_tick(S.trail_ext + S.trail, tick, "up")
                    if S.stop is None or ns < S.stop:
                        S.stop = ns
                        S.trail_stop = True
            pos_arr[j] = S.pos
            entry_arr[j] = S.entry_px
        # -- 6. callbacks / decisions
        if j == n - 1:
            continue
        call = (S.pos != 0) or (active is None) or active[j] or bool(fills_bar)
        if not call:
            continue
        ctx.i = j
        ctx.ts = idx[j]
        ctx.open, ctx.high, ctx.low, ctx.close, ctx.volume = oj, hj, lj, cj, v_[j]
        ctx.bid_vol = bid_[j] if bid_ is not None else None
        ctx.ask_vol = ask_[j] if ask_ is not None else None
        ctx.session_date = sdates[j]
        ctx.session_type = stype[j]
        ctx.bar_in_session = biss[j]
        ctx.is_session_last = is_last[j]
        ctx.minute_of_day = end_min[j]
        ctx.position = S.pos
        ctx.entry_price = S.entry_px if S.pos != 0 else float("nan")
        ctx.stop = S.stop if S.pos != 0 else None
        ctx.target = S.target if S.pos != 0 else None
        ctx.bars_held = S.bars if S.pos != 0 else 0
        ctx.equity = capital + real_cum
        ctx.session_pnl = sess["pnl"]
        ctx.trades_today = sess["trades"]
        ctx.consecutive_losses = sess["cl"]
        for f in fills_bar:
            on_fill(ctx, f)
        out = on_bar(ctx)
        if out is None:
            continue
        if isinstance(out, Order):
            out = [out]
        if order_log is not None:
            # (decision bar, normalised orders): lets the causality harness compare WHAT was decided bar by bar
            order_log.append((j, tuple(_order_key(od) for od in out)))
        for od in out:
            if od.kind == "flatten":
                pend_flat = od.tag or "flatten"
            elif od.kind == "modify":
                pend_mod.append(od)
            else:
                if od.entry in ("limit", "stop") and od.price is None:
                    raise ValueError("limit/stop entry needs price")
                if od.entry in ("limit", "stop"):
                    # adverse: a buy limit / sell stop rounds down, a sell limit / buy stop rounds up
                    od.price = round_tick(od.price, tick, "down" if (od.sign > 0) == (od.entry == "limit") else "up")
                pend_entries.append((od, codes[j], v_[j], cj))

    # ---- assemble result
    realized = np.cumsum(real_inc)
    unreal = pos_arr * (np.asarray(c_) - entry_arr) * pv
    eq = pd.Series(capital + realized + unreal, index=idx, name="equity")
    sd = pd.DatetimeIndex(sdates)
    rets = daily_from_equity(eq, sd, capital)
    costs_d = daily_sum(cost_arr, sd)
    tr = pd.DataFrame(trades, columns=TRADE_COLUMNS) if trades else empty_trades()
    m = dict(meta or {})
    m.update({"mode": "event", "freq": panel.freq, "rejected_orders": dict(rejects), "cost_mult": cost_mult,
              "delta_source": "real" if ("bid_vol" in b and "ask_vol" in b) else "approx_or_none"})
    return RunResult(
        equity=eq, returns_daily=rets, positions=pd.DataFrame({sym: pos_arr}, index=idx), trades=tr,
        costs_daily=costs_d,
        benchmark_daily=panel.benchmark, rf_daily=panel.cash, initial_capital=float(capital), meta=m,
    )
