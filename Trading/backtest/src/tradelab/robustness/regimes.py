"""Regime breakdowns of daily returns: year, volatility terciles, trend, weekday.

Regime labels for day t use information up to t-1 only (shifted), so a regime is knowable in advance.
The market proxy is ``benchmark_daily`` when present, otherwise the strategy's own returns (flagged).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from tradelab.analytics.metrics import daily_returns


def _stats(r: pd.Series, ppy: int) -> dict:
    n = len(r)
    sd = r.std(ddof=1) if n > 1 else float("nan")
    return {"n_days": n, "total_return": float((1 + r).prod() - 1) if n else float("nan"),
            "ann_return": float(r.mean() * ppy) if n else float("nan"),
            "sharpe": float(r.mean() / sd * math.sqrt(ppy)) if n > 1 and sd > 0 else float("nan"),
            "hit_rate": float((r > 0).mean()) if n else float("nan")}


def _table(r: pd.Series, labels: pd.Series, ppy: int, name: str) -> pd.DataFrame:
    rows = {}
    for lab, grp in r.groupby(labels.reindex(r.index), observed=True):
        rows[lab] = _stats(grp, ppy)
    df = pd.DataFrame(rows).T
    df.index.name = name
    return df


def regime_breakdown(result: Any, *, periods_per_year: int = 252, vol_window: int = 20, trend_window: int = 100,
                     market: pd.Series | None = None) -> dict[str, pd.DataFrame]:
    r = daily_returns(result)
    if len(r) < 10:
        return {}
    idx = pd.DatetimeIndex(r.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    r = pd.Series(r.to_numpy(), index=idx)
    mk = market if market is not None else getattr(result, "benchmark_daily", None)
    proxy_is_strategy = mk is None
    m = r if mk is None else pd.Series(mk, dtype=float).reindex(r.index).fillna(0.0)
    out: dict[str, pd.DataFrame] = {}
    out["year"] = _table(r, pd.Series(r.index.year, index=r.index), periods_per_year, "year")
    vol = m.rolling(vol_window, min_periods=max(5, vol_window // 2)).std().shift(1)
    if vol.notna().sum() >= 30:
        q = vol.rank(pct=True)
        lab = pd.Series(np.where(q <= 1 / 3, "low_vol", np.where(q <= 2 / 3, "mid_vol", "high_vol")), index=r.index)
        lab[vol.isna()] = None
        out["volatility"] = _table(r[lab.notna()], lab.dropna(), periods_per_year, "vol_regime")
    curve = (1 + m).cumprod()
    ma = curve.rolling(trend_window, min_periods=max(10, trend_window // 2)).mean()
    up = (curve > ma).shift(1)
    valid = ma.shift(1).notna()
    if valid.sum() >= 30:
        lab = pd.Series(np.where(up, "uptrend", "downtrend"), index=r.index)[valid]
        out["trend"] = _table(r[valid], lab, periods_per_year, "trend_regime")
    wd = pd.Series(r.index.day_name(), index=r.index)
    out["weekday"] = _table(r, wd, periods_per_year, "weekday")
    for t in out.values():
        t.attrs["proxy"] = "strategy" if proxy_is_strategy else "benchmark"
    return out


def regime_summary(tables: dict[str, pd.DataFrame], min_days: int = 20) -> dict:
    """Compact JSON: share of regimes with negative total return and the worst regime."""
    rows = []
    for name, t in tables.items():
        if name == "weekday":
            continue
        for lab, row in t.iterrows():
            if row["n_days"] >= min_days:
                rows.append((name, str(lab), float(row["total_return"]), float(row["sharpe"]) if np.isfinite(row["sharpe"]) else None))
    if not rows:
        return {}
    worst = min(rows, key=lambda x: x[2])
    return {"n_regimes": len(rows), "n_negative": int(sum(1 for x in rows if x[2] < 0)),
            "worst": {"table": worst[0], "label": worst[1], "total_return": worst[2], "sharpe": worst[3]},
            "proxy": next(iter(tables.values())).attrs.get("proxy")}
