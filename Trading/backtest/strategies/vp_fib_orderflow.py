"""Value-area / Fibonacci / order-flow pullback strategy ("context -> location -> confirmation").

Event-mode strategy on 5-minute RTH bars (MNQ / NQ) replicating, as faithfully as OHLCV(+optional
bid/ask volume) data allows, the discretionary method described in the video
"Trading WORLD CHAMPION Reveals the Orderflow Strategy That Won the Robbins Cup" (IQCapital, Chris
"Thraxx" Creamer).  Full rule list, assumptions and optimisation grid: docs/STRATEGY_vp_fib_orderflow.md.

Rule -> transcript quote
------------------------
Overview        "it's context, location, then confirmation."  -> three stages below.
Context         "are we currently in a value up structure, a value down structure, or sideways?" /
                "I typically do not want to go against this type of structure."
                -> ``context_mode`` (value-area migration prior session vs session before, and/or HH/HL swing
                structure of 1H/4H bars built causally from the 5m bars); long only in value-up, short only in
                value-down, sideways = no trade (``trade_sideways=False``).  Gamma ("positive gamma ... selling
                into the rips") needs an options chain: NOT implemented (regime label only in the video).
Location        "anything below value area is discount, anything above it is premium." -> prior-RTH-session
                VAL/VAH (70 %, ``va_pct``) or developing value (``value_source``); ``zone_vs_value``.
                "the fib levels specifically are uh the 705, the 788, and the 886" -> ``fib_shallow``/``fib_deep``
                (default 0.705 / 0.886; 0.618/0.786/0.788 are valid alternatives) on the latest confirmed
                impulse leg (fractal swings: ``swing_tf_minutes``, ``swing_k``).
                "I need to make sure that this is outside of value area." -> ``zone_vs_value="outside"``.
                "The moment ... we end up going below the 886 ... I'm not taking the trade." ->
                ``invalid_level`` / ``invalid_on`` kill the leg before the trigger.
                "I just want to see a swing point ... potentially a sweep." -> ``swing_confirm``.
Confirmation    "I'm identifying absorption happening in discount." -> sell-aggression bar (negative delta, long
                lower wick = volume concentrated at the low) whose low reaches the zone (``abs_*`` params,
                ``delta_source``).  "absorption doesn't mean automatic reversal" -> a flip bar is still needed.
                "when there is an imbalance of 400% or more" -> ``flip_imbalance`` (bar-level ask/bid ratio, real
                bid/ask volume only; footprint per-price imbalance is NOT reproducible).
                "I want it to fail higher up ... And we flip bullish. I'm going long." -> ``confirm_mode=first_flip``;
                "I try again and we fail for the second time and flip again, I'm going long." ->
                ``confirm_mode=second_failure`` (absorption -> flip -> retest that holds the low -> flip).
Entry           market at the next open after the flip bar, or buy stop above the flip-bar high (``entry_mode``).
Stop            "I'm putting my stop loss ... On the other side of the failed sellers." ->
                absorption low - ``stop_buffer_ticks``; skipped if outside [min_stop_ticks, max_stop_ticks].
Target          "Typically, I'm I'm aiming for swing points." -> ``target_mode=swing`` (nearest confirmed swing
                high giving >= ``min_rr``); alternatives fixed R ("1.5 to 2 R"), prior POC, prior VAH.
Management      "maybe move it break even" / "if price does not reclaim value ... move break even or cut the trade"
                -> ``be_at_r``, ``no_reclaim_bars`` + ``no_reclaim_action``.
Session         "I'm really only trading the first hour and a half of New York open" -> ``window_start/end``;
                "I have a hard shutoff time" -> flatten at ``window_end + flatten_extension_min``;
                "20,000 contracts per 5-minute candle" -> ``min_bar_volume`` (x ``volume_scale``);
                "most days I'm taking one or two trades" -> ``max_trades_per_day=2``;
                "stop after two losses in a row" -> ``max_consecutive_losses=2``.
Sizing          "Risk 1% ..." -> ``risk_pct`` of realised equity / (stop distance x point value), ``max_contracts``.
Shorts          not shown in the video; exact mirror (premium above VAH, down-leg, failed-buyer absorption).

Causality: every array built in ``prepare`` at bar i uses only data stamped <= ts[i] (bar-end stamps);
HTF bars are exposed only at their final 5m bar (clock-determined), fractal swings only at pivot + k,
prior-session levels only from completed sessions, ATR/delta/wicks are bar-local or backward-looking.
The short side is computed by running the *same* scan on negated prices (mirror), so long/short logic
cannot diverge.  Assumes RTH-only data (``data.session: rth``).
"""
from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd

from tradelab.data.calendar import freq_to_timedelta, hhmm_to_minutes
from tradelab.features import (atr as atr_fn, bar_imbalance, confirmed_swings, delta as delta_fn,
                               developing_value_area, market_structure, session_profiles)
from tradelab.features.orderflow import has_real_delta
from tradelab.strategy import Order, Params, Strategy, grid, register

RTH_OPEN_MIN = 9 * 60 + 30
RTH_CLOSE_MIN = 16 * 60


class VpFibParams(Params):
    # ---------------- context
    context_mode: Literal["va_migration", "htf_swing", "both", "any", "off"] = grid(
        "any", values=["va_migration", "htf_swing", "both", "any"],
        description="value-up/down classifier: VA migration, HTF HH/HL swings, both must agree, any (conflict=sideways), off")
    htf_minutes: int = grid(60, values=[60, 240], description="higher-timeframe bar length (min) for swing structure")
    htf_swing_k: int = grid(1, values=[1, 2], description="fractal k for HTF swing structure")
    va_migration_rule: Literal["strict", "mid"] = grid("strict", values=["strict", "mid"],
                                                     description="strict: VAL and VAH both higher/lower; mid: VA midpoint")
    trade_sideways: bool = grid(False, values=[False], description="trade both ways when context is sideways")
    sides: Literal["long", "short", "both"] = grid("both", values=["long", "short", "both"])
    va_pct: float = grid(0.70, values=[0.68, 0.70], description="value-area volume share")
    value_source: Literal["prior", "developing"] = grid("prior", values=["prior", "developing"],
                                                       description="VAL/VAH/POC from prior RTH session or developing session")
    # ---------------- location
    swing_tf_minutes: int = grid(5, values=[5, 15], description="timeframe of fractal swings used for fib legs / targets")
    swing_k: int = grid(2, values=[2, 3], description="fractal swing half-window (bars)")
    atr_n: int = 14
    min_leg_atr: float = grid(3.0, values=[2.0, 3.0, 5.0], description="min impulse-leg size in 5m ATR")
    leg_scope: Literal["session", "carry"] = grid("carry", values=["session", "carry"],
                                                 description="session: legs reset each session; carry: may span days")
    fib_shallow: float = grid(0.705, values=[0.618, 0.705], description="shallow edge of the fib zone")
    fib_deep: float = grid(0.886, values=[0.786, 0.886], description="deep edge of the fib zone")
    invalid_level: float = grid(0.886, values=[0.886, 1.0], description="retracement beyond which the pullback is invalid")
    invalid_on: Literal["close", "low"] = grid("close", values=["close", "low"], description="invalidate on close or any wick")
    zone_vs_value: Literal["outside", "discount", "off"] = grid(
        "outside", values=["outside", "discount", "off"],
        description="outside: whole fib zone beyond VAL/VAH; discount: only the absorption bar low beyond it; off")
    swing_confirm: Literal["off", "sweep", "swing", "either"] = grid("either", values=["off", "sweep", "either"],
                                                                   description="require sweep and/or confirmed swing in zone")
    sweep_lookback: int = 6
    # ---------------- confirmation
    delta_source: Literal["auto", "real", "clv", "tick"] = grid("auto", values=["auto"], description="auto = real bid/ask if present else tick rule")
    abs_wick_min: float = grid(0.35, values=[0.25, 0.35, 0.5], description="min lower-wick share of range on the absorption bar")
    abs_delta_pct: float = grid(0.05, values=[0.0, 0.05, 0.15], description="real-delta only: delta/volume <= -x")
    confirm_mode: Literal["first_flip", "second_failure"] = grid("first_flip", values=["first_flip", "second_failure"])
    flip_imbalance: float = grid(0.0, values=[0.0, 2.0, 4.0], description="min ask/bid ratio on the flip bar (real data only; 0=off)")
    max_wait_bars: int = grid(3, values=[2, 3, 5], description="max bars per confirmation stage before the setup expires")
    # ---------------- entry / stop / target
    entry_mode: Literal["market", "stop"] = grid("market", values=["market", "stop"])
    entry_valid_bars: int = 2
    stop_buffer_ticks: int = grid(1, values=[1, 2, 4])
    min_stop_ticks: int = grid(12, values=[8, 12, 20])
    max_stop_ticks: int = grid(240, values=[160, 240, 400])
    target_mode: Literal["swing", "r_multiple", "poc", "vah"] = grid("swing", values=["swing", "r_multiple", "poc"])
    target_r: float = grid(2.0, values=[1.5, 2.0, 3.0], description="R multiple when target_mode=r_multiple")
    min_rr: float = grid(1.0, values=[1.0, 1.5], description="skip trade if target gives less than this R")
    max_target_r: float = grid(0.0, values=[0.0, 3.0], description="cap swing/POC target at this R (0=off)")
    be_at_r: float = grid(0.0, values=[0.0, 1.0, 1.5], description="move stop to breakeven after this many R (0=off)")
    be_offset_ticks: int = 0
    no_reclaim_bars: int = grid(0, values=[0, 6], description="after N bars, if value not reclaimed, act (0=off)")
    no_reclaim_action: Literal["breakeven", "exit"] = "breakeven"
    max_signals_per_leg: int = 1
    # ---------------- session rules
    window_start: str = "09:30"
    window_end: str = grid("11:00", values=["10:30", "11:00", "11:30"])
    flatten_extension_min: int = grid(0, values=[0, 30, 90], description="keep position this long after window_end")
    max_trades_per_day: int = 2
    max_consecutive_losses: int = 2
    min_bar_volume: float = grid(20000.0, values=[0.0, 20000.0], description="min decision-bar volume (MNQ-equivalent contracts)")
    volume_scale: float = 1.0           # multiply bar volume to MNQ-equivalent (NQ: ~4, calibrate on overlap data)
    # ---------------- sizing
    risk_pct: float = 0.01
    max_contracts: int = 20


# =====================================================================================================
# pure helpers (all causal)
# =====================================================================================================
def va_migration_dir(val1, vah1, val2, vah2, rule: str = "strict") -> np.ndarray:
    """+1 value migrating up (prior session VA above the one before), -1 down, 0 overlapping/unknown."""
    val1, vah1, val2, vah2 = (np.asarray(x, float) for x in (val1, vah1, val2, vah2))
    if rule == "mid":
        m1, m2 = (val1 + vah1) / 2, (val2 + vah2) / 2
        up, dn = m1 > m2, m1 < m2
    else:
        up, dn = (val1 > val2) & (vah1 > vah2), (val1 < val2) & (vah1 < vah2)
    ok = np.isfinite(val1) & np.isfinite(vah1) & np.isfinite(val2) & np.isfinite(vah2)
    return np.where(ok & up, 1, np.where(ok & dn, -1, 0)).astype(int)


def aggregate_htf(o, h, l, c, end_min, sess, base_min: int, minutes: int):
    """Aggregate base bars into `minutes` buckets anchored at the 09:30 open.

    Returns (frame, fin_pos): one row per COMPLETE bucket (completeness decided by the clock only, so it is
    prefix-invariant), `fin_pos` = position of its last base bar (the bar at which it becomes known)."""
    n = len(o)
    if minutes <= base_min:
        return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}), np.arange(n)
    start_off = np.asarray(end_min) - base_min - RTH_OPEN_MIN
    key = np.asarray(sess, np.int64) * 10_000 + (start_off // minutes)
    starts = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    ends = np.r_[starts[1:], n] - 1
    em = np.asarray(end_min)[ends]
    fin = (((em - RTH_OPEN_MIN) % minutes) == 0) | (em >= RTH_CLOSE_MIN)
    frame = pd.DataFrame({
        "open": np.asarray(o)[starts], "high": np.maximum.reduceat(h, starts), "low": np.minimum.reduceat(l, starts),
        "close": np.asarray(c)[ends]})
    return frame[fin].reset_index(drop=True), ends[fin]


def swing_events(high, low, k: int, pos_map, n: int) -> dict:
    """Confirmed fractal swings mapped to base-bar positions.  Event at base bar i = pivot confirmed at i."""
    sw = confirmed_swings(pd.Series(np.asarray(high, float)), pd.Series(np.asarray(low, float)), k)
    out = {x: np.zeros(n, bool) for x in ("swh_new", "swl_new")}
    out.update({x: np.full(n, np.nan) for x in ("swh_px", "swl_px")})
    out.update({x: np.zeros(n, np.int64) for x in ("swh_pos", "swl_pos")})
    pos_map = np.asarray(pos_map)
    for kind, new, px, pp in (("swh", "swing_high_new", "last_swing_high", "last_swing_high_pos"),
                              ("swl", "swing_low_new", "last_swing_low", "last_swing_low_pos")):
        j = np.flatnonzero(sw[new].to_numpy())
        if len(j) == 0:
            continue
        i = pos_map[j]
        out[kind + "_new"][i] = True
        out[kind + "_px"][i] = sw[px].to_numpy()[j]
        out[kind + "_pos"][i] = pos_map[sw[pp].to_numpy()[j].astype(int)]
    return out


def htf_structure(o, h, l, c, end_min, sess, base_min: int, minutes: int, k: int) -> np.ndarray:
    """+1/-1/0 swing structure (HH&HL / LH&LL) of HTF bars, forward-filled to base bars once known."""
    n = len(o)
    fr, fin_pos = aggregate_htf(o, h, l, c, end_min, sess, base_min, minutes)
    out = np.full(n, np.nan)
    if len(fr) > 2 * k + 2:
        sw = confirmed_swings(fr["high"], fr["low"], k)
        out[fin_pos] = market_structure(sw).to_numpy()
    return pd.Series(out).ffill().fillna(0.0).to_numpy().astype(int)


def mirror_inputs(inp: dict, ctx_ok) -> dict:
    """Negated-price view so that the long scan serves shorts (premium/VAH/down-leg/failed buyers)."""
    m = dict(inp)
    m["open"], m["close"] = -inp["open"], -inp["close"]
    m["high"], m["low"] = -inp["low"], -inp["high"]
    m["delta_pct"] = -inp["delta_pct"]
    m["imb_buy"] = inp["imb_sell"]
    m["imb_sell"] = inp["imb_buy"]
    m["val"], m["vah"], m["poc"] = -inp["vah"], -inp["val"], -inp["poc"]
    m["swh_new"], m["swl_new"] = inp["swl_new"], inp["swh_new"]
    m["swh_px"], m["swl_px"] = -inp["swl_px"], -inp["swh_px"]
    m["swh_pos"], m["swl_pos"] = inp["swl_pos"], inp["swh_pos"]
    m["ctx_ok"] = ctx_ok
    return m


def scan_long(inp: dict, p: VpFibParams, tick: float) -> dict:
    """Stateful single-pass setup scanner for the LONG side (shorts run on mirrored inputs).

    inp arrays (len n): open high low close volume delta_pct imb_buy ctx_ok(bool) in_window(bool) sess(int)
    val vah poc atr swh_new swh_px swh_pos swl_new swl_px swl_pos; scalar inp['real'] (real bid/ask delta?).
    Returns arrays: sig (bool at the flip bar), stop, target, ref, entry_px, abs_low, zone_lo, zone_hi, leg_low, leg_high.
    """
    n = len(inp["close"])
    o, h, l, c = (inp[k].tolist() for k in ("open", "high", "low", "close"))
    v = inp["volume"].tolist()
    dp = inp["delta_pct"].tolist()
    imb = inp["imb_buy"].tolist()
    ok = inp["ctx_ok"].tolist()
    win = inp["in_window"].tolist()
    sess = inp["sess"].tolist()
    val, poc, vah = inp["val"].tolist(), inp["poc"].tolist(), inp["vah"].tolist()
    atr = inp["atr"].tolist()
    shn, shp, shpos = inp["swh_new"].tolist(), inp["swh_px"].tolist(), inp["swh_pos"].tolist()
    sln, slp, slpos = inp["swl_new"].tolist(), inp["swl_px"].tolist(), inp["swl_pos"].tolist()
    real = bool(inp.get("real", False))

    nan = float("nan")
    out = {k: np.full(n, nan) for k in ("stop", "target", "ref", "entry_px", "abs_low", "zone_lo", "zone_hi", "leg_low", "leg_high")}
    sig = np.zeros(n, bool)

    lows: list = []     # (pivot_pos, px) confirmed swing lows
    highs: list = []    # px of confirmed swing highs
    leg = None          # [L, H, H_pivot_pos]
    nsig = 0
    stage, stage_i, abs_low, sweep_ok = 0, -1, nan, False
    last_sess = None
    min_vol = p.min_bar_volume
    vscale = p.volume_scale
    buf = p.stop_buffer_ticks * tick
    wait = p.max_wait_bars
    sweep_n = p.sweep_lookback

    for i in range(n):
        if sess[i] != last_sess:
            last_sess = sess[i]
            if p.leg_scope == "session":
                leg, stage = None, 0
                lows.clear()
                highs.clear()
        if sln[i]:
            lows.append((slpos[i], slp[i]))
            if len(lows) > 60:
                del lows[0]
        if shn[i]:
            hpx = shp[i]
            highs.append(hpx)
            if len(highs) > 60:
                del highs[0]
            lo_px = None
            for pos, px in reversed(lows):
                if pos < shpos[i]:
                    lo_px = px
                    break
            a = atr[i]
            if lo_px is not None and hpx > lo_px and a == a and (hpx - lo_px) >= p.min_leg_atr * a:
                if leg is None or hpx > leg[1]:
                    leg = [lo_px, hpx, shpos[i]]
                    stage, nsig = 0, 0
        if leg is not None and h[i] > leg[1]:     # price made a new high: leg stale until a new pivot confirms
            leg, stage = None, 0
        if leg is None:
            continue

        L, H = leg[0], leg[1]
        R = H - L
        ztop, zbot = H - p.fib_shallow * R, H - p.fib_deep * R
        inval = H - p.invalid_level * R
        out["zone_lo"][i], out["zone_hi"][i], out["leg_low"][i], out["leg_high"][i] = zbot, ztop, L, H
        if (c[i] if p.invalid_on == "close" else l[i]) < inval:
            leg, stage = None, 0
            continue
        if not ok[i]:
            stage = 0
            continue

        vl = val[i]
        if p.zone_vs_value == "outside":
            zone_ok = vl == vl and ztop < vl
        elif p.zone_vs_value == "discount":
            zone_ok = vl == vl and l[i] < vl
        else:
            zone_ok = True

        if stage >= 1:
            if i - stage_i > wait or l[i] < abs_low:
                stage = 0

        rng = h[i] - l[i]
        d = dp[i]
        if stage == 0:
            if not zone_ok or rng <= 0 or l[i] > ztop:
                continue
            wick = (min(o[i], c[i]) - l[i]) / rng
            sells = (d <= -p.abs_delta_pct) if real else (d < 0)
            if sells and wick >= p.abs_wick_min:
                stage, stage_i, abs_low = 1, i, l[i]
                sweep_ok = i >= sweep_n and l[i] < min(l[i - sweep_n:i])
            continue

        bullish = c[i] > o[i] and (d > 0) and (not real or d >= 0)
        flip_ok = bullish
        if flip_ok and real and p.flip_imbalance > 0:
            r = imb[i]
            flip_ok = r == r and r >= p.flip_imbalance

        fire = False
        if stage == 1 and flip_ok:
            if p.confirm_mode == "first_flip":
                fire = True
            else:
                stage, stage_i = 2, i
        elif stage == 2 and c[i] < o[i]:
            stage, stage_i = 3, i
        elif stage == 3 and flip_ok:
            fire = True
        if not fire:
            continue

        # ---------------- trigger -> checks, stop, target
        if not win[i] or nsig >= p.max_signals_per_leg:
            continue
        if min_vol > 0 and v[i] * vscale < min_vol:
            continue
        sw_ok = True
        if p.swing_confirm != "off":
            has_sw = False
            for pos, px in reversed(lows):
                if pos <= leg[2]:
                    break
                if px <= ztop:
                    has_sw = True
                    break
            sw_ok = {"sweep": sweep_ok, "swing": has_sw, "either": sweep_ok or has_sw}[p.swing_confirm]
        if not sw_ok:
            continue
        stop = abs_low - buf
        ref = c[i] if p.entry_mode == "market" else h[i] + tick
        risk = ref - stop
        if risk <= 0 or not (p.min_stop_ticks <= risk / tick <= p.max_stop_ticks):
            continue
        tgt = nan
        if p.target_mode == "r_multiple":
            tgt = ref + p.target_r * risk
        elif p.target_mode == "swing":
            cand = [x for x in highs if x > ref and (x - ref) >= p.min_rr * risk]
            tgt = min(cand) if cand else nan
        else:
            lvl = poc[i] if p.target_mode == "poc" else vah[i]
            tgt = lvl if (lvl == lvl and lvl > ref and (lvl - ref) >= p.min_rr * risk) else nan
        if tgt != tgt:
            continue
        if p.max_target_r > 0:
            tgt = min(tgt, ref + p.max_target_r * risk)
        sig[i] = True
        out["stop"][i], out["target"][i], out["ref"][i] = stop, tgt, ref
        out["entry_px"][i] = ref if p.entry_mode == "stop" else nan
        out["abs_low"][i] = abs_low
        nsig += 1
        stage = 0
    out["sig"] = sig
    return out


# =====================================================================================================
@register
class VpFibOrderflow(Strategy):
    name = "vp_fib_orderflow"
    mode = "event"
    Params = VpFibParams
    warmup_sessions = 10
    description = ("Context (value migration / HTF structure) -> location (discount below VAL + fib 0.705-0.886 outside value) "
                   "-> confirmation (absorption then bullish delta flip). Stop below failed-seller low, target next swing.")

    # ---------------------------------------------------------------- prepare
    def prepare(self, data):
        self._risk0 = None
        self._be_done = False
        p: VpFibParams = self.params
        b = data[data.primary]
        spec = data.specs[data.primary]
        tick = spec.tick_size or 0.01
        n = len(b)
        base_min = int(freq_to_timedelta(data.freq).total_seconds() // 60)
        loc = b.index.tz_convert(spec.tz)
        end_min = (loc.hour * 60 + loc.minute).to_numpy()
        sess = pd.factorize(b["session_date"])[0]
        o, h, l, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        vol = b["volume"].to_numpy(float)

        # ---- value levels
        prof = session_profiles(b, tick, p.va_pct)
        sdates = pd.DatetimeIndex(b["session_date"])

        def prior(k, col):
            s = prof[col].shift(k).reindex(sdates)
            return s.to_numpy(float)

        val1, vah1, poc1 = prior(1, "val"), prior(1, "vah"), prior(1, "poc")
        val2, vah2 = prior(2, "val"), prior(2, "vah")
        if p.value_source == "developing":
            dv = developing_value_area(b, tick, p.va_pct)
            val, vah, poc = dv["dev_val"].to_numpy(), dv["dev_vah"].to_numpy(), dv["dev_poc"].to_numpy()
        else:
            val, vah, poc = val1, vah1, poc1

        # ---- context
        va_dir = va_migration_dir(val1, vah1, val2, vah2, p.va_migration_rule)
        htf_dir = (htf_structure(o, h, l, c, end_min, sess, base_min, p.htf_minutes, p.htf_swing_k)
                   if p.context_mode in ("htf_swing", "both", "any") else np.zeros(n, int))
        if p.context_mode == "va_migration":
            ctx = va_dir
        elif p.context_mode == "htf_swing":
            ctx = htf_dir
        elif p.context_mode == "both":
            ctx = np.where(va_dir == htf_dir, va_dir, 0)
        elif p.context_mode == "any":
            ctx = np.where(va_dir == 0, htf_dir, np.where(htf_dir == 0, va_dir, np.where(va_dir == htf_dir, va_dir, 0)))
        else:
            ctx = None
        if ctx is None:
            long_ok = short_ok = np.ones(n, bool)
        else:
            long_ok = (ctx == 1) | ((ctx == 0) & p.trade_sideways)
            short_ok = (ctx == -1) | ((ctx == 0) & p.trade_sideways)
        long_ok = long_ok & (p.sides in ("long", "both"))
        short_ok = short_ok & (p.sides in ("short", "both"))

        # ---- order flow
        real = has_real_delta(b) and p.delta_source in ("auto", "real")
        method = "real" if real else ("tick" if p.delta_source in ("auto", "real") else p.delta_source)
        d = delta_fn(b, method).to_numpy(float)
        dpct = np.where(vol > 0, d / np.where(vol > 0, vol, 1.0), 0.0)
        imb = bar_imbalance(b)
        imb_buy = imb["ask_bid_ratio"].to_numpy(float)
        imb_sell = imb["bid_ask_ratio"].to_numpy(float)

        # ---- swings, ATR, window
        if p.swing_tf_minutes <= base_min:
            fr = pd.DataFrame({"high": h, "low": l})
            pos_map = np.arange(n)
        else:
            fr, pos_map = aggregate_htf(o, h, l, c, end_min, sess, base_min, p.swing_tf_minutes)
        ev = swing_events(fr["high"].to_numpy(), fr["low"].to_numpy(), p.swing_k, pos_map, n)
        atr = atr_fn(b["high"], b["low"], b["close"], p.atr_n).to_numpy()
        w0, w1 = hhmm_to_minutes(p.window_start), hhmm_to_minutes(p.window_end)
        in_window = (end_min >= w0) & (end_min < w1)

        inp = dict(open=o, high=h, low=l, close=c, volume=vol, delta_pct=dpct, imb_buy=imb_buy, imb_sell=imb_sell,
                   ctx_ok=long_ok, in_window=in_window, sess=sess, val=val, vah=vah, poc=poc, atr=atr, real=real, **ev)
        feats = {k: np.full(n, np.nan) for k in ("sig_side", "sig_stop", "sig_target", "sig_ref", "sig_entry_px", "sig_abs_low",
                                                  "zone_lo", "zone_hi", "leg_low", "leg_high")}
        feats["sig_side"] = np.zeros(n)
        if p.sides in ("long", "both"):
            r = scan_long(inp, p, tick)
            m = r["sig"]
            feats["sig_side"][m] = 1
            for k in ("stop", "target", "ref", "entry_px", "abs_low"):
                feats["sig_" + k][m] = r[k][m]
            feats["zone_lo"], feats["zone_hi"] = r["zone_lo"].copy(), r["zone_hi"].copy()
            feats["leg_low"], feats["leg_high"] = r["leg_low"].copy(), r["leg_high"].copy()
        if p.sides in ("short", "both"):
            r = scan_long(mirror_inputs(inp, short_ok), p, tick)
            m = r["sig"] & (feats["sig_side"] == 0)
            feats["sig_side"][m] = -1
            for k in ("stop", "target", "ref", "entry_px", "abs_low"):
                feats["sig_" + k][m] = -r[k][m]
            has = ~np.isnan(r["zone_lo"]) & np.isnan(feats["zone_lo"])
            feats["zone_lo"][has], feats["zone_hi"][has] = -r["zone_hi"][has], -r["zone_lo"][has]
            feats["leg_low"][has], feats["leg_high"][has] = -r["leg_high"][has], -r["leg_low"][has]
        feats.update(val=val, vah=vah, poc=poc, ctx_dir=(np.zeros(n) if ctx is None else ctx.astype(float)))
        return feats

    # ---------------------------------------------------------------- on_bar
    def on_bar(self, ctx):
        p: VpFibParams = self.params
        if ctx.position != 0:
            return self._manage(ctx)
        self._risk0 = None
        self._be_done = False
        side = ctx.f("sig_side")
        if side == 0 or side != side:
            return None
        if ctx.trades_today >= p.max_trades_per_day or ctx.consecutive_losses >= p.max_consecutive_losses:
            return None
        tick = ctx.spec.tick_size or 0.01
        stop, target, ref = ctx.f("sig_stop"), ctx.f("sig_target"), ctx.f("sig_ref")
        risk_pts = abs(ref - stop)
        if risk_pts <= 0:
            return None
        qty = math.floor(ctx.equity * p.risk_pct / (risk_pts * ctx.spec.point_value) + 1e-9)
        qty = min(qty, p.max_contracts)
        if qty < 1:
            return None
        buy = side > 0
        if p.entry_mode == "stop":
            return Order("buy" if buy else "sell", qty=qty, entry="stop", price=ctx.f("sig_entry_px"), stop=stop,
                         target=target, valid_bars=p.entry_valid_bars, tag="vpfib_long" if buy else "vpfib_short")
        return Order("buy" if buy else "sell", qty=qty, stop=stop, target=target, tag="vpfib_long" if buy else "vpfib_short")

    def _manage(self, ctx):
        p: VpFibParams = self.params
        tick = ctx.spec.tick_size or 0.01
        if ctx.minute_of_day >= hhmm_to_minutes(p.window_end) + p.flatten_extension_min:
            return Order.flatten("window_end")
        if ctx.stop is None:
            return None
        sgn = 1 if ctx.position > 0 else -1
        if self._risk0 is None:
            self._risk0 = abs(ctx.entry_price - ctx.stop)
            self._be_done = False
        if self._be_done or self._risk0 <= 0:
            return None
        ep = ctx.entry_price
        be_stop = ep + sgn * p.be_offset_ticks * tick
        if p.be_at_r > 0:
            fav = (ctx.high - ep) if sgn > 0 else (ep - ctx.low)
            if fav >= p.be_at_r * self._risk0:
                self._be_done = True
                return Order.modify(stop=be_stop, tag="breakeven")
        if p.no_reclaim_bars > 0 and ctx.bars_held >= p.no_reclaim_bars:
            lvl = ctx.f("val") if sgn > 0 else ctx.f("vah")
            reclaimed = lvl == lvl and ((ctx.close >= lvl) if sgn > 0 else (ctx.close <= lvl))
            if not reclaimed:
                if p.no_reclaim_action == "exit":
                    return Order.flatten("no_reclaim")
                if (ctx.close - ep) * sgn >= tick:
                    self._be_done = True
                    return Order.modify(stop=be_stop, tag="breakeven")
        return None
