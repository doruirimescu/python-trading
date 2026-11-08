"""Probabilistic / Deflated Sharpe ratio and minimum track-record length.

Bailey & Lopez de Prado (2012) "The Sharpe Ratio Efficient Frontier", (2014) "The Deflated Sharpe Ratio".
All Sharpe ratios here are **non-annualised** (per observation). ``gamma3`` = skewness,
``gamma4`` = NON-excess kurtosis (normal = 3). Euler-Mascheroni constant for E[max SR].
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats as sps

EULER_GAMMA = 0.5772156649015328606


def sr_stats(returns: Sequence[float] | pd.Series) -> dict:
    """Per-period Sharpe (mean/std, ddof=1), T, skew (biased moment), non-excess kurtosis."""
    x = np.asarray(pd.Series(returns, dtype=float).dropna())
    T = len(x)
    if T < 3 or x.std(ddof=1) == 0:
        return {"sr": float("nan"), "T": T, "skew": float("nan"), "kurt": float("nan")}
    return {"sr": float(x.mean() / x.std(ddof=1)), "T": T,
            "skew": float(sps.skew(x, bias=True)), "kurt": float(sps.kurtosis(x, fisher=False, bias=True))}


def psr_from_stats(sr: float, T: int, skew: float = 0.0, kurt: float = 3.0, sr_benchmark: float = 0.0) -> float:
    """PSR(SR*) = Phi( (SR - SR*) sqrt(T-1) / sqrt(1 - g3 SR + (g4-1)/4 SR^2) )."""
    denom_sq = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if T < 2 or denom_sq <= 0 or not np.isfinite(sr):
        return float("nan")
    z = (sr - sr_benchmark) * math.sqrt(T - 1) / math.sqrt(denom_sq)
    return float(sps.norm.cdf(z))


def psr(returns: Sequence[float] | pd.Series, sr_benchmark: float = 0.0) -> float:
    """PSR of per-period returns against a per-period benchmark Sharpe (default 0)."""
    s = sr_stats(returns)
    return psr_from_stats(s["sr"], s["T"], s["skew"], s["kurt"], sr_benchmark)


def expected_max_sr(n_trials: int, sr_variance: float) -> float:
    """E[max_N SR] under the null: sqrt(V) * ((1-g) Phi^-1(1-1/N) + g Phi^-1(1-1/(N e)))."""
    if n_trials <= 1:
        return 0.0
    n = float(n_trials)
    return float(math.sqrt(max(sr_variance, 0.0)) * (
        (1 - EULER_GAMMA) * sps.norm.ppf(1 - 1 / n) + EULER_GAMMA * sps.norm.ppf(1 - 1 / (n * math.e))))


def dsr_from_stats(sr: float, T: int, skew: float, kurt: float, n_trials: int, sr_variance: float) -> float:
    return psr_from_stats(sr, T, skew, kurt, sr_benchmark=expected_max_sr(n_trials, sr_variance))


def dsr(returns: Sequence[float] | pd.Series, n_trials: int, sr_variance: float) -> float:
    """Deflated Sharpe: PSR against SR0 = E[max SR] over ``n_trials`` with cross-trial per-period
    SR variance ``sr_variance``."""
    s = sr_stats(returns)
    return dsr_from_stats(s["sr"], s["T"], s["skew"], s["kurt"], n_trials, sr_variance)


def min_trl_from_stats(sr: float, skew: float = 0.0, kurt: float = 3.0, sr_benchmark: float = 0.0,
                       alpha: float = 0.05) -> float:
    """MinTRL = 1 + (1 - g3 SR + (g4-1)/4 SR^2) (z_{1-alpha} / (SR - SR*))^2 (observations)."""
    if not np.isfinite(sr) or sr <= sr_benchmark:
        return float("inf")
    z = sps.norm.ppf(1 - alpha)
    return float(1 + (1 - skew * sr + (kurt - 1) / 4 * sr**2) * (z / (sr - sr_benchmark)) ** 2)


def min_trl(returns: Sequence[float] | pd.Series, sr_benchmark: float = 0.0, alpha: float = 0.05) -> float:
    s = sr_stats(returns)
    return min_trl_from_stats(s["sr"], s["skew"], s["kurt"], sr_benchmark, alpha)


def sr_variance_from_returns_matrix(m: pd.DataFrame) -> float:
    """Cross-sectional variance of per-period Sharpe ratios across trial columns."""
    sr = m.mean() / m.std(ddof=1)
    return float(sr.replace([np.inf, -np.inf], np.nan).var(ddof=1))


# ----------------------------------------------------------------- append-only trial ledger


def trial_ledger_append(path: str | Path, record: dict[str, Any]) -> None:
    """Append one JSON line. Never rewrites existing content (append-only)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    from tradelab.analytics.metrics import jsonable
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(jsonable(record), sort_keys=True) + "\n")


def trial_ledger_read(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def count_trials(path: str | Path, strategy: str | None = None) -> int:
    """Total trials recorded (sum of ``n_trials`` per record, default 1), optionally per strategy."""
    n = 0
    for rec in trial_ledger_read(path):
        if strategy is None or rec.get("strategy") == strategy:
            n += int(rec.get("n_trials", 1))
    return n
