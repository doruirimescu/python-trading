"""Daily SMA crossover (vector mode). Long when fast SMA > slow SMA, optionally short otherwise."""
from __future__ import annotations

import pandas as pd

from tradelab.features import sma
from tradelab.strategy import Params, Strategy, grid, register


class SmaCrossParams(Params):
    fast: int = grid(20, low=5, high=50, step=5, description="fast SMA length (bars)")
    slow: int = grid(100, low=60, high=200, step=20, description="slow SMA length (bars)")
    long_only: bool = True
    weight: float = 1.0


@register
class SmaCross(Strategy):
    name = "sma_cross"
    mode = "vector"
    Params = SmaCrossParams
    description = "Hold weight when SMA(fast) > SMA(slow) on close; flat (or short) otherwise. Engine delays the fill."

    def signals(self, data):
        p = self.params
        close = data.field("close")
        out = {}
        for s in close.columns:
            f, sl = sma(close[s], p.fast), sma(close[s], p.slow)
            ok = f.notna() & sl.notna()
            up = (f > sl) & ok
            dn = (f < sl) & ok
            pos = up.astype(float) * p.weight
            if not p.long_only:
                pos = pos - dn.astype(float) * p.weight
            out[s] = pos
        return pd.DataFrame(out, index=close.index)
