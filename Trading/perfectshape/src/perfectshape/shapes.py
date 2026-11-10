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


def range_band(Y: np.ndarray, q: float, axis=0):
    """Symmetric trading band of each column: (lo, mid, hi) = median -+ h, where h is the smaller half of the
    [q, 100-q] percentile band. A one-sided spike stretches only one half, so it cannot widen the band."""
    plo, mid, phi = np.percentile(Y, [q, 50, 100 - q], axis=axis)
    h = np.minimum(mid - plo, phi - mid)
    return mid - h, mid, mid + h


def band_trades(Y: np.ndarray, lo: np.ndarray, mid: np.ndarray, hi: np.ndarray, exit: str = "mid",
                segments: int = 1):
    """Completed band trades per column, the log move they capture at minimum, and their spread over time.

    A trade opens when the curve leaves the band (<= lo: long, >= hi: short) and closes when it next reaches
    the median (exit="mid") or the opposite edge (exit="opposite"). Returns (n_trades, capture, coverage,
    adverse): capture is the summed edge-to-exit distance (overshoot beyond the edge is not counted);
    coverage is the share of ``segments`` equal parts of the window in which at least one trade closed;
    adverse is the worst move against an open trade, measured from the edge where it opened.
    """
    T = Y.shape[0]
    cols = np.arange(Y.shape[1])[None, :]
    rows = np.arange(T)[:, None]

    def ffill(state):                        # 9 = no event on this bar: carry the last state forward
        idx = np.where(state != 9, rows, -1)
        last = np.maximum.accumulate(idx, axis=0)
        return np.where(last >= 0, state[np.maximum(last, 0), cols], 9)

    edge = np.where(Y <= lo, -1, np.where(Y >= hi, 1, 9))
    if exit == "opposite":
        f = ffill(edge)
        prev, cur = f[:-1], f[1:]
        c_lo = (prev == -1) & (cur == 1)
        c_hi = (prev == 1) & (cur == -1)
        gain_lo = gain_hi = hi - lo
    else:
        above = Y >= mid
        cross = np.zeros_like(above)
        cross[1:] = above[1:] != above[:-1]
        f = ffill(np.where(edge != 9, edge, np.where(cross, 0, 9)))
        prev, cur = f[:-1], f[1:]
        c_lo = (prev == -1) & (cur != -1)               # long closed: crossed back up through the median
        c_hi = (prev == 1) & (cur != 1)                 # short closed
        gain_lo, gain_hi = mid - lo, hi - mid
    against = np.where(f == -1, lo - Y, np.where(f == 1, Y - hi, 0.0))
    adverse = np.maximum(against.max(axis=0), 0.0)
    closed = c_lo | c_hi                                # (T-1, m): a trade closed on this bar
    n_lo, n_hi = c_lo.sum(axis=0), c_hi.sum(axis=0)
    bounds = np.linspace(0, closed.shape[0], segments + 1).astype(int)
    per_seg = np.add.reduceat(closed, bounds[:-1], axis=0) if closed.shape[0] else np.zeros((segments, Y.shape[1]))
    coverage = (per_seg > 0).sum(axis=0) / segments
    return n_lo + n_hi, n_lo * gain_lo + n_hi * gain_hi, coverage, adverse


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
    """A bounded, oscillating basket that pays to trade: flat drift, and frequent, large swings across a band.

    Successor of Trading.algo.ranker.RobustRangeScorer: percentile band (outlier-robust), a drift penalty
    (quadratic trend component vs band height, so arcs count as drift too) and an oscillation reward. The
    reward is the **harvest**: the annual log move captured by trading the band (enter when the curve
    leaves it, exit at the median or the opposite edge, see :func:`band_trades`), so more trades and wider
    bands both score higher, and its **coverage**: the share of the window's parts in which a trade closed, so
    one-off excursions do not pass for a repeatable range, and its **pain**: the worst move against an open
    trade beyond the edge, in half-bands (a squeeze that runs far past the band before reverting is a range
    nobody could have held). The band is symmetric around the median (:func:`range_band`) so a one-sided
    spike can neither widen it nor earn an outsized credit.
    score = sqrt(flatness * coverage * (1 - exp(-harvest / range_harvest_scale))
                 * exp(-max(0, pain - 1) / range_pain_scale)).
    The band is fitted on the same window it trades: a descriptive, in-sample measure.
    """

    name = "range"
    objective = "range_ratio"

    def score(self, curves, cfg):
        Y = to_space(curves, cfg.space)
        q = cfg.range_band_pct
        lo, mid, hi = range_band(Y, q)
        band = hi - lo
        scale = 1.0 if cfg.space == "log" else np.maximum(np.abs(mid), 1e-12)   # -> relative moves
        height = band / scale
        # band size as tradable moves: buy at the bottom edge and sell at the top edge, or the reverse
        if cfg.space == "log":
            swing_up, swing_down = np.expm1(band), -np.expm1(-band)
        else:
            swing_up = band / np.maximum(np.abs(lo), 1e-12)
            swing_down = band / np.maximum(np.abs(hi), 1e-12)
        drift_curve = poly_fit(Y, 2)
        drift = drift_curve.max(axis=0) - drift_curve.min(axis=0)
        drift_ratio = drift / np.maximum(band, 1e-12)
        n_trades, capture, coverage, adverse = band_trades(Y, lo, mid, hi, cfg.range_exit, cfg.range_segments)
        pain = adverse / np.maximum((hi - lo) / 2, 1e-12)     # worst move against a trade, in half-bands
        capture = capture / scale
        years = max(Y.shape[0] - 1, 1) / cfg.periods_per_year
        harvest = capture / years                                             # log move per year
        per_trade = np.where(n_trades > 0, capture / np.maximum(n_trades, 1), 0.0)
        harvest_score = 1.0 - np.exp(-harvest / cfg.range_harvest_scale)
        flat = np.clip(1.0 - drift_ratio, 0, 1)
        pain_score = np.exp(-np.maximum(pain - 1.0, 0.0) / cfg.range_pain_scale)
        soft = np.sqrt(flat * coverage * harvest_score * pain_score)
        gate = (height >= cfg.min_range_height) & (drift_ratio <= cfg.max_range_drift)
        rel = np.expm1 if cfg.space == "log" else (lambda x: x)
        return ScoreResult(
            score=np.where(gate, soft, 0.0),
            soft=soft * np.clip(height / max(cfg.min_range_height, 1e-9), 0, 1),
            metrics={"harvest": rel(harvest), "trades_per_year": n_trades / years, "per_trade": rel(per_trade),
                     "coverage": coverage, "pain": pain, "worst_against": -np.expm1(-adverse / scale)
                     if cfg.space == "log" else adverse / scale,
                     "swing_up": swing_up, "swing_down": swing_down, "height": height,
                     "drift_ratio": drift_ratio, "swings": zone_swings(Y, q, 100 - q).astype(float)},
        )

    def channel(self, fit_curve, cfg):
        Y = to_space(fit_curve, cfg.space)
        lo, _, hi = range_band(Y, cfg.range_band_pct)
        pad = 0.25 * (hi - lo)
        return lambda t: (lo - pad, hi + pad)
