"""Strategy base class, Order and Fill."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal

import numpy as np
import pandas as pd

from .params import Params

if TYPE_CHECKING:
    from ..data.panel import Panel
    from .ctx import BarContext

Features = dict  # name -> np.ndarray aligned to the primary symbol's bars (len == n_bars)


@dataclass
class Order:
    """Order emitted at the CLOSE of bar t (decision), executed from bar t+1.

    side: 'buy' | 'sell'.  Exactly one of qty / risk_pct for entries.
    entry: 'market' (fills at open t+1) | 'limit' | 'stop' (working from t+1 for `valid_bars` bars).
    stop/target: absolute prices attached to the position once filled (R = |entry - stop|).
    trailing: trailing-stop distance in price points (ratchets at bar close, effective next bar).
    time_stop_bars: exit at the close of the bar when the position has been held that many bars
                    (entry bar counts as 1).
    kind: 'entry' (default) | 'flatten' (market close at next open) | 'modify' (update stop/target of open position).
    """

    side: Literal["buy", "sell"] = "buy"
    qty: float | None = None
    risk_pct: float | None = None
    entry: Literal["market", "limit", "stop"] = "market"
    price: float | None = None
    stop: float | None = None
    target: float | None = None
    trailing: float | None = None
    time_stop_bars: int | None = None
    valid_bars: int = 1
    tag: str = ""
    kind: Literal["entry", "flatten", "modify"] = "entry"

    @classmethod
    def flatten(cls, tag: str = "") -> "Order":
        return cls(kind="flatten", tag=tag)

    @classmethod
    def modify(cls, stop: float | None = None, target: float | None = None, tag: str = "") -> "Order":
        return cls(kind="modify", stop=stop, target=target, tag=tag)

    @property
    def sign(self) -> int:
        return 1 if self.side == "buy" else -1


@dataclass(frozen=True)
class Fill:
    ts: pd.Timestamp
    side: str
    qty: float
    price: float
    reason: str          # entry | stop | target | time_stop | flatten | session_end | end_of_data | trailing
    tag: str = ""
    is_entry: bool = False
    pnl: float = 0.0     # net trade P&L for exits


class Strategy(ABC):
    name: ClassVar[str] = ""
    Params: ClassVar[type[Params]] = Params
    mode: ClassVar[Literal["vector", "event"]] = "vector"
    description: ClassVar[str] = ""

    def __init__(self, params: Params | None = None):
        self.params = params if params is not None else self.Params()

    # ---- vector mode: target position (weight or units) per bar, decided at the close of that bar
    def signals(self, data: "Panel") -> pd.DataFrame:
        raise NotImplementedError

    # ---- event mode
    def prepare(self, data: "Panel") -> Features:
        """Causal vectorised precompute. Returned arrays/Series/DataFrame must be aligned to the primary symbol's bars."""
        return {}

    def on_bar(self, ctx: "BarContext") -> Order | list[Order] | None:
        return None

    def on_fill(self, ctx: "BarContext", fill: Fill) -> None:
        return None


def features_to_arrays(feats, index: pd.Index) -> Features:
    """Normalise prepare() output to dict[str, np.ndarray]."""
    if feats is None:
        return {}
    if isinstance(feats, pd.DataFrame):
        feats = {c: feats[c] for c in feats.columns}
    out = {}
    for k, v in feats.items():
        if isinstance(v, pd.Series):
            if len(v) != len(index) or not v.index.equals(index):
                v = v.reindex(index)
            v = v.to_numpy()
        elif isinstance(v, pd.DataFrame):
            raise TypeError(f"feature {k!r} is a DataFrame; flatten to named columns")
        out[k] = np.asarray(v)
        if len(out[k]) != len(index):
            raise ValueError(f"feature {k!r} length {len(out[k])} != n_bars {len(index)}")
    return out
