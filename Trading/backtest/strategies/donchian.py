from tradelab.features import donchian
from tradelab.strategy import Params, Strategy, grid, register
import pandas as pd

class DonchianParams(Params):                     # extra=forbid; grid() gives optimiser hints
    n: int = grid(20, low=10, high=60, step=10)

@register
class Donchian(Strategy):
    name, mode = "donchian", "vector"
    Params = DonchianParams
    description = "Long above the prior-n-bar high, flat below the prior-n-bar low."
    def signals(self, data):                      # data: Panel. returns DataFrame bar index x symbol
        out = {}
        for s in data.symbols:
            b = data[s]
            ch = donchian(b["high"], b["low"], self.params.n)   # channel of PREVIOUS n bars
            state = pd.Series(float("nan"), index=b.index)
            state[b["close"] > ch["upper"]] = 1.0
            state[b["close"] < ch["lower"]] = 0.0
            out[s] = state.ffill().fillna(0.0)
        return pd.DataFrame(out, index=data.index)
