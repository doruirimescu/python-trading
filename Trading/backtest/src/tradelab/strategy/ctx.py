"""BarContext: everything a strategy may see at the close of bar i (features only up to i)."""
from __future__ import annotations



class BarContext:
    """Mutable object reused by the engine for each bar -> do NOT store references to it.

    Attributes (all valid at the close of bar i):
      i, ts (bar end, UTC), ts_local (exchange tz), open/high/low/close/volume, bid_vol, ask_vol,
      session_date, session_type, bar_in_session, is_session_last, minute_of_day (local end-minute)
      position (signed qty), entry_price, stop, target, bars_held, equity (realized, flat-based),
      session_pnl, trades_today, consecutive_losses, spec, symbol
    Use ``f(name)`` for the feature value at i and ``hist(name, n)`` for the last n values (<= i).
    """

    __slots__ = ("_feats", "i", "ts", "open", "high", "low", "close", "volume", "bid_vol", "ask_vol",
                 "session_date", "session_type", "bar_in_session", "is_session_last", "minute_of_day",
                 "position", "entry_price", "stop", "target", "bars_held", "equity", "session_pnl",
                 "trades_today", "consecutive_losses", "spec", "symbol", "_ts_arr", "_tz")

    def __init__(self, feats, spec, symbol, ts_arr, tz):
        self._feats = feats
        self.spec = spec
        self.symbol = symbol
        self._ts_arr = ts_arr
        self._tz = tz

    @property
    def ts_local(self):
        return self.ts.tz_convert(self._tz)

    def f(self, name: str):
        return self._feats[name][self.i]

    __call__ = f

    def hist(self, name: str, n: int):
        a = self._feats[name]
        lo = max(0, self.i + 1 - n)
        return a[lo: self.i + 1]

    @property
    def is_flat(self) -> bool:
        return self.position == 0

    @property
    def unrealized_points(self) -> float:
        return 0.0 if self.position == 0 else (self.close - self.entry_price) * (1 if self.position > 0 else -1)
