"""Test helpers: hand-built panels and scripted strategies."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tradelab.config.schema import ExecCfg, RiskRules
from tradelab.data.instruments import get_instrument
from tradelab.data.panel import Panel
from tradelab.data.sessions import tag_sessions
from tradelab.strategy import Params, Strategy

ET = "America/New_York"


def intraday_panel(bars, *, symbol="MNQ", start="2024-01-02 09:35", freq="5m", step_min=5, spec_over=None) -> Panel:
    """bars: list of (o, h, l, c[, vol]) -> panel with bar-END stamps starting at `start` ET (end of 1st bar)."""
    n = len(bars)
    idx = pd.date_range(pd.Timestamp(start, tz=ET), periods=n, freq=f"{step_min}min").tz_convert("UTC")
    arr = np.array([list(b) + [1000.0] * (5 - len(b)) for b in bars], float)
    df = pd.DataFrame(arr, index=idx, columns=["open", "high", "low", "close", "volume"])
    df.index.name = "ts"
    spec = get_instrument(symbol, spec_over)
    df = tag_sessions(df, spec, freq)
    return Panel({symbol: df}, freq, {symbol: spec})


def daily_panel(opens, closes, *, symbol="SPY", start="2024-01-02", highs=None, lows=None, volume=1e6, cash=None) -> Panel:
    n = len(closes)
    days = pd.bdate_range(start, periods=n)
    o, c = np.asarray(opens, float), np.asarray(closes, float)
    h = np.maximum(o, c) if highs is None else np.asarray(highs, float)
    l = np.minimum(o, c) if lows is None else np.asarray(lows, float)
    idx = (days + pd.Timedelta(hours=16)).tz_localize(ET).tz_convert("UTC")
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": volume}, index=idx)
    df.index.name = "ts"
    spec = get_instrument(symbol)
    df = tag_sessions(df, spec, "1d")
    p = Panel({symbol: df}, "1d", {symbol: spec})
    if cash is not None:
        p.cash = pd.Series(cash, index=pd.DatetimeIndex(df["session_date"].unique()))
    return p


class Scripted(Strategy):
    """Event strategy that emits pre-programmed orders at given bar indices."""
    name = "_scripted"
    mode = "event"

    def __init__(self, script: dict | None = None, params: Params | None = None):
        super().__init__(params)
        self.script = script or {}
        self.fills = []

    def on_bar(self, ctx):
        s = self.script.get(ctx.i)
        if callable(s):
            return s(ctx)
        return s

    def on_fill(self, ctx, fill):
        self.fills.append(fill)


def ex(**kw) -> ExecCfg:
    risk = kw.pop("risk", {})
    return ExecCfg(risk=RiskRules(**risk), **kw)
