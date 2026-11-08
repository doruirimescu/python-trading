"""Shape definitions: how a basket curve is scored and which weight objective builds it.

Every metric here is vectorised over columns: ``curves`` is (T, m), one candidate basket curve per column,
each starting at 1.0. Scores are in [0, 1]; 0 means a hard gate failed (wrong direction, too flat,
too tight, drifting range...). ``soft`` is the same score without the gates, used to pick search seeds.

Add a shape by subclassing :class:`Shape` and decorating it with :func:`register_shape`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from perfectshape.config import ScoringConfig

SHAPES: dict[str, "Shape"] = {}


def register_shape(cls):
    SHAPES[cls.name] = cls()
    return cls


def get_shape(name: str) -> "Shape":
    return SHAPES[name]


@dataclass
class ScoreResult:
    score: np.ndarray                 # (m,) gated score in [0, 1]
    soft: np.ndarray                  # (m,) ungated score
    metrics: dict[str, np.ndarray]    # name -> (m,)


def to_space(curves: np.ndarray, space: str) -> np.ndarray:
    if space == "log":
        return np.log(np.clip(curves, 1e-9, None))
    return curves


def _tau(T: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, T)


def linear_fit(Y: np.ndarray):
    """OLS of each column on [1, tau]. Returns intercept a, total move b (over the window), residuals, r2."""
    T = Y.shape[0]
    tau = _tau(T)
    tc = tau - tau.mean()
    ym = Y.mean(axis=0)
    b = (tc @ (Y - ym)) / (tc @ tc)
    a = ym - b * tau.mean()
    resid = Y - (a[None, :] + tau[:, None] * b[None, :])
    ss_res = (resid ** 2).sum(axis=0)
    ss_tot = ((Y - ym) ** 2).sum(axis=0)
    r2 = np.where(ss_tot > 0, 1.0 - ss_res / np.maximum(ss_tot, 1e-300), 0.0)
    return a, b, resid, r2


def poly_fit(Y: np.ndarray, degree: int = 2) -> np.ndarray:
    """Least-squares polynomial (in tau) fitted values per column."""
    T = Y.shape[0]
    P = np.vander(_tau(T) * 2 - 1, degree + 1, increasing=True)
    Q, _ = np.linalg.qr(P)
    return Q @ (Q.T @ Y)


def max_drawdown(Y: np.ndarray) -> np.ndarray:
    return (np.maximum.accumulate(Y, axis=0) - Y).max(axis=0)


def max_rally(Y: np.ndarray) -> np.ndarray:
    return (Y - np.minimum.accumulate(Y, axis=0)).max(axis=0)


def zone_swings(Y: np.ndarray, lo_q: float = 20, hi_q: float = 80) -> np.ndarray:
    """Number of alternations between the lower zone (<= lo_q pct) and the upper zone (>= hi_q pct)."""
    lo = np.percentile(Y, lo_q, axis=0)
    hi = np.percentile(Y, hi_q, axis=0)
    zone = np.where(Y >= hi, 1, np.where(Y <= lo, -1, 0))
    T = Y.shape[0]
    idx = np.where(zone != 0, np.arange(T)[:, None], -1)
    last = np.maximum.accumulate(idx, axis=0)
    cols = np.arange(Y.shape[1])[None, :]
    filled = np.where(last >= 0, zone[np.maximum(last, 0), cols], 0)
    changes = (filled[1:] != filled[:-1]) & (filled[:-1] != 0)
    return changes.sum(axis=0)


class Shape:
    name: ClassVar[str]
    objective: ClassVar[str]          # "trend_tstat" or "range_ratio" (see solver.py)
    direction: ClassVar[int] = 0      # +1 up, -1 down, 0 none

    def score(self, curves: np.ndarray, cfg: ScoringConfig) -> ScoreResult:
        raise NotImplementedError

    def channel(self, fit_curve: np.ndarray, cfg: ScoringConfig):
        """Callable(t_index_from_fit_start) -> (lower, upper) bounds the shape must stay inside."""
        raise NotImplementedError


class _Trend(Shape):
    objective = "trend_tstat"

    def score(self, curves, cfg):
        Y = to_space(curves, cfg.space)
        T = Y.shape[0]
        a, b, resid, r2 = linear_fit(Y)
        if cfg.space == "log":
            annual = np.expm1(b * cfg.periods_per_year / max(T - 1, 1))
        else:
            annual = (b / np.where(np.abs(a) > 1e-12, a, 1e-12)) * cfg.periods_per_year / max(T - 1, 1)
        adverse = max_drawdown(Y) if self.direction > 0 else max_rally(Y)
        adverse_ratio = adverse / np.maximum(np.abs(b), 1e-12)
        r2c = np.clip(r2, 0, 1)
        soft = np.sqrt(r2c * np.clip(1.0 - adverse_ratio, 0, 1))
        gate = (np.sign(b) == self.direction) & (np.abs(annual) >= cfg.min_annual_return)
        return ScoreResult(
            score=np.where(gate, soft, 0.0),
            soft=np.where(np.sign(b) == self.direction, soft, 0.0),
            metrics={"r2": r2, "annual_return": annual, "total_move": b, "adverse_ratio": adverse_ratio,
                     "max_dev": np.abs(resid).max(axis=0)},
        )

    def channel(self, fit_curve, cfg):
        Y = to_space(fit_curve[:, None], cfg.space)
        a, b, resid, _ = linear_fit(Y)
        T = len(fit_curve)
        lo_dev, hi_dev = resid.min(), resid.max()
        slope = b[0] / max(T - 1, 1)

        def bounds(t):
            line = a[0] + slope * t
            return line + lo_dev, line + hi_dev
        return bounds


@register_shape
class Uptrend(_Trend):
    name = "uptrend"
    direction = 1


@register_shape
class Downtrend(_Trend):
    name = "downtrend"
    direction = -1


@register_shape
class Range(Shape):
    """A bounded, oscillating basket: flat drift, a band wide enough to trade, and several swings across it.

    Successor of Trading.algo.ranker.RobustRangeScorer: percentile boundaries (outlier-robust), a drift
    penalty (here: quadratic trend component vs band height, so arcs count as drift too) and an
    oscillation reward (here: completed swings between the lower and upper zones).
    """

    name = "range"
    objective = "range_ratio"

    def score(self, curves, cfg):
        Y = to_space(curves, cfg.space)
        p5, p50, p95 = np.percentile(Y, [5, 50, 95], axis=0)
        band = p95 - p5
        height = band if cfg.space == "log" else band / np.maximum(np.abs(p50), 1e-12)
        drift_curve = poly_fit(Y, 2)
        drift = drift_curve.max(axis=0) - drift_curve.min(axis=0)
        drift_ratio = drift / np.maximum(band, 1e-12)
        swings = zone_swings(Y)
        swing_score = 1.0 - np.exp(-swings / 3.0)
        flat = np.clip(1.0 - drift_ratio, 0, 1)
        soft = np.sqrt(flat * swing_score)
        gate = (height >= cfg.min_range_height) & (drift_ratio <= cfg.max_range_drift)
        return ScoreResult(
            score=np.where(gate, soft, 0.0),
            soft=soft * np.clip(height / max(cfg.min_range_height, 1e-9), 0, 1),
            metrics={"height": height, "drift_ratio": drift_ratio, "swings": swings.astype(float)},
        )

    def channel(self, fit_curve, cfg):
        Y = to_space(fit_curve, cfg.space)
        p5, p95 = np.percentile(Y, [5, 95])
        pad = 0.25 * (p95 - p5)
        return lambda t: (p5 - pad, p95 + pad)
