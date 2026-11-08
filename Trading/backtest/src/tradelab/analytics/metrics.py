"""Core performance metrics computed from a ``RunResult`` (duck-typed, see ARCHITECTURE section 5).

Conventions
-----------
* All ratios are computed on **daily-aggregated** returns (``result.returns_daily``); never on
  bar returns. Annualisation uses ``periods_per_year`` (252 equities/futures, 365 crypto).
* Returns, drawdowns, VaR are fractions (0.05 == 5%).
* Output of :func:`compute_metrics` is JSON-serialisable (NaN/inf -> ``None``).
"""
from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from ..util.span import years_span

# --------------------------------------------------------------------------- helpers


def jsonable(obj: Any) -> Any:
    """Recursively convert numpy/pandas objects to plain JSON types (NaN/inf -> None)."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        ts = pd.Timestamp(obj)
        return None if pd.isna(ts) else ts.isoformat()
    if isinstance(obj, pd.Timedelta):
        return obj.total_seconds()
    if isinstance(obj, pd.DataFrame):
        return jsonable(obj.reset_index().to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def trade_col(trades: pd.DataFrame | None, *names: str) -> pd.Series | None:
    """Case-insensitive column lookup; returns None when no candidate exists."""
    if trades is None:
        return None
    lower = {str(c).lower(): c for c in trades.columns}
    for n in names:
        c = lower.get(n.lower())
        if c is not None:
            return trades[c]
    return None


def daily_returns(result: Any) -> pd.Series:
    r = pd.Series(result.returns_daily, dtype=float).dropna()
    r = r[~r.index.duplicated(keep="last")].sort_index()
    return r


def aligned_rf(result: Any, index: pd.Index) -> pd.Series:
    rf = getattr(result, "rf_daily", None)
    if rf is None:
        return pd.Series(0.0, index=index)
    return pd.Series(rf, dtype=float).reindex(index).fillna(0.0)


def _safe_div(a: float, b: float) -> float:
    if b is None or a is None or not np.isfinite(b) or b == 0:
        return float("nan")
    return float(a) / float(b)


# --------------------------------------------------------------------------- primitives


def sharpe_ratio(r: pd.Series, rf: pd.Series | float = 0.0, periods_per_year: int = 252) -> float:
    ex = (r - rf).dropna()
    if len(ex) < 2:
        return float("nan")
    sd = ex.std(ddof=1)
    return _safe_div(ex.mean(), sd) * math.sqrt(periods_per_year) if sd > 0 else float("nan")


def sortino_ratio(r: pd.Series, rf: pd.Series | float = 0.0, periods_per_year: int = 252) -> float:
    """Sortino with target = rf; downside deviation = sqrt(mean(min(x,0)^2)) over ALL periods."""
    ex = (r - rf).dropna()
    if len(ex) < 2:
        return float("nan")
    dd = math.sqrt(float(np.mean(np.minimum(ex.to_numpy(), 0.0) ** 2)))
    return _safe_div(ex.mean(), dd) * math.sqrt(periods_per_year)


def drawdown_series(r: pd.Series) -> pd.Series:
    """Drawdown (<=0) of the compounded daily curve, starting from 1.0."""
    curve = (1.0 + r).cumprod()
    peak = np.maximum.accumulate(np.concatenate([[1.0], curve.to_numpy()]))[1:]
    return pd.Series(curve.to_numpy() / peak - 1.0, index=r.index)


def drawdown_stats(r: pd.Series) -> dict:
    """Max drawdown, its dates, longest underwater spell (sessions & calendar days), recovery time."""
    out: dict[str, Any] = {
        "max_drawdown": float("nan"), "max_dd_peak_date": None, "max_dd_trough_date": None,
        "max_dd_recovery_date": None, "max_dd_recovered": None,
        "max_dd_duration_days": float("nan"), "max_dd_duration_sessions": float("nan"),
        "time_to_recovery_days": None, "ulcer_index": float("nan"),
    }
    if len(r) == 0:
        return out
    dd = drawdown_series(r)
    curve = (1.0 + r).cumprod()
    out["ulcer_index"] = float(math.sqrt(float(np.mean(dd.to_numpy() ** 2))))
    out["max_drawdown"] = float(dd.min())
    trough = dd.idxmin()
    prior = curve.loc[:trough]
    peak_val = max(1.0, float(prior.max()))
    peak_date = prior.idxmax() if float(prior.max()) >= 1.0 else None
    after = curve.loc[trough:]
    rec = after[after >= peak_val]
    out["max_dd_peak_date"] = peak_date
    out["max_dd_trough_date"] = trough
    out["max_dd_recovered"] = bool(len(rec) > 0)
    if len(rec):
        out["max_dd_recovery_date"] = rec.index[0]
        try:
            out["time_to_recovery_days"] = float((rec.index[0] - trough).days)
        except Exception:  # non-datetime index
            out["time_to_recovery_days"] = float(len(after.loc[: rec.index[0]]) - 1)
    # longest underwater spell
    under = (dd < 0).to_numpy()
    best_n = cur_n = 0
    best_days = 0.0
    start_i = 0
    idx = dd.index
    for i, u in enumerate(under):
        if u:
            if cur_n == 0:
                start_i = i
            cur_n += 1
            if cur_n > best_n:
                best_n = cur_n
            try:
                span = float((idx[i] - idx[max(start_i - 1, 0)]).days)
            except Exception:
                span = float(cur_n)
            best_days = max(best_days, span)
        else:
            cur_n = 0
    out["max_dd_duration_sessions"] = float(best_n)
    out["max_dd_duration_days"] = float(best_days)
    return out


def var_cvar(r: pd.Series, level: float = 0.95) -> dict:
    """Historical and Cornish-Fisher VaR / CVaR as positive loss fractions (per day)."""
    x = r.to_numpy()
    tag = int(round(level * 100))
    out = {f"var_{tag}_hist": float("nan"), f"cvar_{tag}_hist": float("nan"), f"var_{tag}_cf": float("nan")}
    if len(x) < 5:
        return out
    a = 1 - level
    q = float(np.quantile(x, a))
    out[f"var_{tag}_hist"] = -q
    tail = x[x <= q]
    out[f"cvar_{tag}_hist"] = float(-tail.mean()) if len(tail) else -q
    mu, sd = x.mean(), x.std(ddof=1)
    s, k = float(sps.skew(x, bias=False)), float(sps.kurtosis(x, fisher=True, bias=False))
    z = sps.norm.ppf(a)
    zcf = z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24 - (2 * z**3 - 5 * z) * s**2 / 36
    out[f"var_{tag}_cf"] = float(-(mu + zcf * sd))
    return out


# --------------------------------------------------------------------------- main entry


def compute_metrics(result: Any, *, periods_per_year: int = 252) -> dict:
    """Full metric dict (JSON-serialisable). Sections: flat return/risk metrics plus
    ``trades``, ``rmultiple``, ``benchmark`` sub-dicts and ``meta``."""
    from .benchmark import benchmark_metrics
    from .rmultiple import r_multiple_stats
    from .trade_stats import trade_stats

    ppy = periods_per_year
    r = daily_returns(result)
    rf = aligned_rf(result, r.index)
    n = len(r)
    m: dict[str, Any] = {"periods_per_year": ppy, "n_days": n, "initial_capital": float(result.initial_capital)}
    if n:
        m["start"], m["end"] = r.index[0], r.index[-1]
    total = float((1 + r).prod() - 1) if n else float("nan")
    years = years_span(r.index, ppy) if n else float("nan")   # calendar span, not n/252
    cagr = (1 + total) ** (1 / years) - 1 if n and years > 0 and 1 + total > 0 else float("nan")
    vol = float(r.std(ddof=1) * math.sqrt(ppy)) if n > 1 else float("nan")
    dd = drawdown_stats(r)
    eq = getattr(result, "equity", None)
    eq_end = float(eq.iloc[-1]) if eq is not None and len(eq) else float("nan")
    m.update(
        total_return=total, cagr=cagr, annual_vol=vol,
        annual_mean_return=float(r.mean() * ppy) if n else float("nan"),
        sharpe=sharpe_ratio(r, rf, ppy), sortino=sortino_ratio(r, rf, ppy),
        final_equity=eq_end,
        net_pnl_equity=eq_end - float(result.initial_capital) if np.isfinite(eq_end) else float("nan"),
    )
    m.update(dd)
    m["calmar"] = _safe_div(cagr, abs(dd["max_drawdown"])) if np.isfinite(dd["max_drawdown"]) else float("nan")
    m["mar"] = m["calmar"]  # MAR = CAGR / |max DD| since inception (same definition here)
    if eq is not None and len(eq) > 1:
        e = pd.Series(eq, dtype=float).dropna()
        m["max_drawdown_bars"] = float((e / e.cummax() - 1).min())
    m["skew"] = float(sps.skew(r, bias=False)) if n > 2 else float("nan")
    m["kurtosis_excess"] = float(sps.kurtosis(r, fisher=True, bias=False)) if n > 3 else float("nan")
    m.update(var_cvar(r, 0.95))
    m.update(var_cvar(r, 0.99))
    if n:
        m.update(best_day=float(r.max()), best_day_date=r.idxmax(), worst_day=float(r.min()), worst_day_date=r.idxmin(),
                 hit_rate_days=float((r > 0).mean()), positive_days=int((r > 0).sum()), negative_days=int((r < 0).sum()))
    costs = getattr(result, "costs_daily", None)
    if costs is not None and len(costs):
        m["total_costs"] = float(pd.Series(costs, dtype=float).sum())
    pos = getattr(result, "positions", None)
    if pos is not None and len(pos):
        p = pos.to_numpy(dtype=float)
        m["exposure"] = float((np.abs(p).sum(axis=1) > 0).mean())
        years_p = max(years, 1e-9) if n else float("nan")
        m["turnover_per_year"] = float(np.abs(np.diff(p, axis=0)).sum() / years_p) if len(p) > 1 else 0.0
    m["trades"] = trade_stats(result.trades, n_days=n)
    m["rmultiple"] = r_multiple_stats(result.trades)
    m["benchmark"] = benchmark_metrics(result, ppy)
    meta = dict(getattr(result, "meta", {}) or {})
    m["meta"] = meta
    return jsonable(m)
