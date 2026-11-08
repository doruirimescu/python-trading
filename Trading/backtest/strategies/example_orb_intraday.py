"""Opening-range breakout (event mode) - minimal example of the event API.

After the opening range (first `or_minutes` of RTH) completes, go long on a close above the range high
(short below the low) with stop at the opposite side of the range and target `rr` R.  Use together with
execution.risk (trade_window, max_trades_per_day) and execution.flatten_at in the YAML.
"""
from __future__ import annotations

import numpy as np

from tradelab.strategy import Order, Params, Strategy, grid, register

RTH_OPEN_MIN = 9 * 60 + 30


class OrbParams(Params):
    or_minutes: int = grid(30, values=[15, 30, 60], description="opening range length in minutes")
    rr: float = grid(2.0, low=1.0, high=3.0, step=0.5, description="target in R multiples")
    risk_pct: float = 0.005
    min_range_ticks: int = 8
    allow_short: bool = True


@register
class OrbIntraday(Strategy):
    name = "orb_intraday"
    mode = "event"
    Params = OrbParams
    description = "Opening range breakout with fixed R target; risk-% sizing; one trade per day via risk rules."

    def prepare(self, data):
        p = self.params
        b = data[data.primary]
        loc = b.index.tz_convert(data.specs[data.primary].tz)
        end_min = loc.hour * 60 + loc.minute
        in_or = np.asarray(end_min <= RTH_OPEN_MIN + p.or_minutes) & (b["session_type"] == "RTH").to_numpy()
        g = b["session_date"]
        or_hi = b["high"].where(in_or).groupby(g).cummax().groupby(g).ffill()   # causal: cummax then carry
        or_lo = b["low"].where(in_or).groupby(g).cummin().groupby(g).ffill()
        done = np.asarray(end_min >= RTH_OPEN_MIN + p.or_minutes) & (b["session_type"] == "RTH").to_numpy()
        return {"or_high": or_hi, "or_low": or_lo, "or_done": done, "_active": done}

    def on_bar(self, ctx):
        if ctx.position != 0 or ctx.trades_today > 0:
            return None
        hi, lo = ctx.f("or_high"), ctx.f("or_low")
        tick = ctx.spec.tick_size or 0.01
        if not (hi == hi and lo == lo) or hi - lo < self.params.min_range_ticks * tick:
            return None
        c = ctx.close
        if c > hi:
            return Order("buy", risk_pct=self.params.risk_pct, stop=lo, target=c + self.params.rr * (c - lo), tag="orb_long")
        if c < lo and self.params.allow_short:
            return Order("sell", risk_pct=self.params.risk_pct, stop=hi, target=c - self.params.rr * (hi - c), tag="orb_short")
        return None
