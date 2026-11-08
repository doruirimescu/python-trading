"""Per-period tables: year, month, weekday, hour-of-day, session type, plus R breakdowns."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .metrics import daily_returns, trade_col
from .rmultiple import r_breakdowns

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _agg(r: pd.Series, key) -> pd.DataFrame:
    g = r.groupby(key)
    return pd.DataFrame({
        "return": g.apply(lambda s: float((1 + s).prod() - 1)),
        "mean_daily": g.mean(), "vol_daily": g.std(ddof=1),
        "hit_rate": g.apply(lambda s: float((s > 0).mean())), "n_days": g.size(),
    })


def periodic_tables(result: Any, tz: str | None = None) -> dict[str, pd.DataFrame]:
    """Tables keyed by name. Always: year, month (year x month matrix), month_long, weekday.
    Intraday (>1 equity bar per day): hour_of_day (bar P&L in currency). If trades have
    ``session_type``: session_type. Plus R breakdown tables when trades exist."""
    r = daily_returns(result)
    out: dict[str, pd.DataFrame] = {}
    if len(r):
        idx = pd.DatetimeIndex(r.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        r = pd.Series(r.to_numpy(), index=idx)
        out["year"] = _agg(r, r.index.year).rename_axis("year")
        ym = _agg(r, [r.index.year, r.index.month])["return"]
        mat = ym.unstack(level=1).reindex(columns=range(1, 13))
        mat.columns = _MONTHS
        mat.index.name = "year"
        out["month"] = mat
        out["month_long"] = ym.rename("return").reset_index().set_axis(["year", "month", "return"], axis=1)
        wd = _agg(r, r.index.dayofweek)
        wd.index = [_DOW[i] for i in wd.index]
        out["weekday"] = wd.rename_axis("weekday")
    eq = getattr(result, "equity", None)
    meta = getattr(result, "meta", {}) or {}
    tzname = tz or meta.get("tz") or meta.get("exchange_tz") or "UTC"
    if eq is not None and len(eq) > 2:
        e = pd.Series(eq, dtype=float)
        if isinstance(e.index, pd.DatetimeIndex):
            days = e.index.tz_convert("UTC") if e.index.tz is not None else e.index
            per_day = e.groupby(days.normalize()).size()
            if per_day.median() > 1:
                pnl = e.diff().fillna(0.0)
                ix = e.index.tz_convert(tzname) if e.index.tz is not None else e.index
                h = pnl.groupby(ix.hour).agg(["sum", "mean", "count"])
                h.columns = ["pnl_sum", "pnl_mean_per_bar", "n_bars"]
                out["hour_of_day"] = h.rename_axis("hour")
    tr = getattr(result, "trades", None)
    if tr is not None and len(tr):
        st = trade_col(tr, "session_type")
        pnl = trade_col(tr, "net_pnl")
        if st is not None and pnl is not None:
            d = pd.DataFrame({"s": st.astype(str), "p": pd.Series(pnl, dtype=float)})
            g = d.groupby("s")["p"]
            out["session_type"] = pd.DataFrame({
                "n": g.size(), "net_pnl": g.sum(), "avg_pnl": g.mean(),
                "hit_rate": g.apply(lambda s: float((s > 0).mean()))}).rename_axis("session_type")
        for k, v in r_breakdowns(tr, tz=tzname).items():
            out[k] = v
    return out
