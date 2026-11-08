"""Test strategy: long (fixed 1 contract) when close breaks above the PRIOR session's high; short below prior low.
Features depend on the previous session, so a window run needs warm-up history."""
from tradelab.strategy import Order, Params, Strategy, register


class PdbParams(Params):
    stop_ticks: int = 40


@register
class PriorDayBrk(Strategy):
    name = "prior_day_brk"
    mode = "event"
    Params = PdbParams
    description = "test: prior-session high/low breakout, qty 1"

    def prepare(self, data):
        b = data[data.primary]
        g = b.groupby("session_date")
        day_hi, day_lo = g["high"].max(), g["low"].min()
        prev_hi = day_hi.shift(1).reindex(b["session_date"]).to_numpy()
        prev_lo = day_lo.shift(1).reindex(b["session_date"]).to_numpy()
        return {"prev_hi": prev_hi, "prev_lo": prev_lo}

    def on_bar(self, ctx):
        hi, lo = ctx.f("prev_hi"), ctx.f("prev_lo")
        if ctx.position != 0 or ctx.trades_today > 0 or hi != hi:
            return None
        tick = ctx.spec.tick_size
        if ctx.close > hi:
            return Order("buy", qty=1, stop=ctx.close - self.params.stop_ticks * tick)
        if ctx.close < lo:
            return Order("sell", qty=1, stop=ctx.close + self.params.stop_ticks * tick)
        return None
