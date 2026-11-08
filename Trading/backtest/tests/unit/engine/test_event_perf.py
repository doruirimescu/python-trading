import time

import pytest

from tradelab.config import DataCfg, ExecCfg
from tradelab.data import load_panel
from tradelab.engine import run_event
from tradelab.strategy import Order, Strategy


class Sparse(Strategy):
    """Realistic activity: opening-range style, a few trades per day (uses the `_active` fast path)."""
    name = "_sparse"
    mode = "event"

    def prepare(self, data):
        b = data[data.primary]
        sma = b["close"].rolling(60).mean()
        return {"sma": sma, "_active": (b["bar_in_session"] == 20).to_numpy()}

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.close > ctx.f("sma"):
            return Order("buy", qty=1, stop=ctx.close - 20, target=ctx.close + 30)


def _timed(years_start, years_end):
    p = load_panel(DataCfg(source="synthetic", symbols=["MNQ"], freq="1m", start=years_start, end=years_end))
    t0 = time.perf_counter()
    r = run_event(p, Sparse(), ExecCfg(slippage_ticks=1), 100_000.0)
    return len(p.index), time.perf_counter() - t0, r


def test_event_engine_100k_bars_reasonable():
    n, dt, r = _timed("2021-01-04", "2021-12-31")
    assert n > 90_000 and len(r.trades) > 50
    assert dt < 10.0, f"{n} bars took {dt:.1f}s"


@pytest.mark.perf
def test_event_engine_1m_bars():
    n, dt, r = _timed("2012-01-03", "2023-12-29")
    print(f"\n{n} bars, {len(r.trades)} trades: {dt:.1f}s")
    assert n > 1_000_000 and dt < 60.0
