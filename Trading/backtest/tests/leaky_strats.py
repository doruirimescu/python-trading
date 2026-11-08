"""Deliberately leaky strategies (tests only, NOT registered). The harness MUST flag all of them."""
import numpy as np

from tradelab.strategy import Order, Strategy


class LeakyVecFuture(Strategy):
    """Reads the next bar's return."""
    name = "_leaky_vec_future"
    mode = "vector"

    def signals(self, data):
        c = data.field("close")
        return np.sign(c.shift(-1) - c).fillna(0.0)


class LeakyVecGlobalStat(Strategy):
    """Uses a statistic of the whole sample (look-ahead through normalisation)."""
    name = "_leaky_vec_global"
    mode = "vector"

    def signals(self, data):
        c = data.field("close")
        return (c > c.mean()).astype(float)


class LeakyEventFutureFeature(Strategy):
    name = "_leaky_event_future"
    mode = "event"

    def prepare(self, data):
        b = data[data.primary]
        return {"fut_up": (b["close"].shift(-1) > b["close"]).astype(float).to_numpy()}

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.f("fut_up") == 1.0:
            return Order("buy", qty=1, time_stop_bars=1)


class LeakyEventSessionAggregate(Strategy):
    """Uses the session's FINAL high on every bar of the session (end-of-session aggregate)."""
    name = "_leaky_event_session_agg"
    mode = "event"

    def prepare(self, data):
        b = data[data.primary]
        return {"sess_high": b.groupby("session_date")["high"].transform("max")}

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.close >= ctx.f("sess_high") - 1 * ctx.spec.tick_size:
            return Order("buy", qty=1, time_stop_bars=2)


class LeakyEventShiftedBack(Strategy):
    """Poison-only leak: peeks at the last bar of the data via iloc[-1]."""
    name = "_leaky_event_last_bar"
    mode = "event"

    def prepare(self, data):
        b = data[data.primary]
        return {"rel": (b["close"] / b["close"].iloc[-1]).to_numpy()}

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.f("rel") < 1.0:
            return Order("buy", qty=1, time_stop_bars=2)


class LeakyEventStashedPanel(Strategy):
    """LEAK invisible to feature checks: stashes the panel's closes in prepare() and reads c[i+1] inside on_bar.

    Its prepared features are causal (all zeros); only the ORDER emitted at the last bar before the cut betrays it.
    """
    name = "_leaky_event_stashed_panel"
    mode = "event"

    def prepare(self, data):
        self._c = data[data.primary]["close"].to_numpy()
        return {"zero": np.zeros(len(self._c))}

    def on_bar(self, ctx):
        i = ctx.i
        if ctx.position == 0 and i + 1 < len(self._c) and self._c[i + 1] > self._c[i] * 1.0005:
            return Order("buy", qty=1, time_stop_bars=1)


class LeakyEventLateStash(LeakyEventStashedPanel):
    """Same stash leak, but only active late in the dataset (the first max_bars bars are clean)."""
    name = "_leaky_event_late_stash"

    def on_bar(self, ctx):
        import pandas as pd
        if ctx.ts < pd.Timestamp("2023-04-03", tz="UTC"):
            return None
        return super().on_bar(ctx)


class LeakyEventStashedBenchmark(Strategy):
    """Reads TODAY's benchmark return (known only at the end of the day) from a stashed panel reference."""
    name = "_leaky_event_stashed_benchmark"
    mode = "event"

    def prepare(self, data):
        self._bench = data.benchmark
        return {"zero": np.zeros(len(data[data.primary]))}

    def on_bar(self, ctx):
        import pandas as pd
        r = self._bench.get(pd.Timestamp(ctx.session_date), 0.0)
        if ctx.position == 0 and r > 0:
            return Order("buy", qty=1, time_stop_bars=1)


class LeakyEventStashedCash(Strategy):
    """Reads TOMORROW's risk-free rate from a stashed panel reference."""
    name = "_leaky_event_stashed_cash"
    mode = "event"

    def prepare(self, data):
        self._cash = data.cash
        return {"zero": np.zeros(len(data[data.primary]))}

    def on_bar(self, ctx):
        import pandas as pd
        i = self._cash.index.searchsorted(pd.Timestamp(ctx.session_date), side="right")
        if ctx.position == 0 and i < len(self._cash) and self._cash.iloc[i] > 0.0001:
            return Order("buy", qty=1, time_stop_bars=1)
