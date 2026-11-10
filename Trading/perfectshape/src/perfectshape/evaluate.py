"""Duration and holdout evaluation of found baskets, and the final ranking.

A basket is held as fixed shares (bought with its fit-window weights); a basket ratio (ratio mode) holds
both legs as fixed shares and its value is numerator / denominator. Its value curve is re-scored on every
window of the ladder ending at the fit end; **duration** is the longest window whose score clears
``scoring.threshold``: how long the basket has been tracing the shape.

**Alive**: the holdout bars (after the fit end, never seen by the search) must stay inside the shape's
channel from the duration window: above the lower trend channel for an uptrend, below the upper one for a
downtrend, inside the padded band for a range.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from perfectshape.config import RankingConfig, ScoringConfig
from perfectshape.data.panel import Panel
from perfectshape.search import Basket, penalised
from perfectshape.shapes import Shape, range_band, to_space


@dataclass
class Result:
    basket: Basket
    duration: int
    score: float                                   # at the duration window (or best window if duration 0)
    metrics: dict[str, float]
    window_scores: dict[int, float]
    alive: bool
    holdout_return: float
    weights_now: list[float]                       # drifted weights at the last bar (numerator leg in ratio mode)
    chart_start: int                               # panel row where the chart curve starts
    curve: np.ndarray = field(repr=False, default=None)  # value from chart_start to the last bar, starts at 1.0
    fit_end: int = 0
    den_weights_now: list[float] = field(default_factory=list)
    ref_window: int = 0                            # window that score / metrics / channel / chart describe


class _Legs:
    """Fixed-share legs of a basket: value = close[:, mi] @ sh, divided by the denominator leg if any."""

    def __init__(self, b: Basket, sym_idx: dict[str, int]):
        self.mi = np.array([sym_idx[m] for m in b.members])
        self.sh = np.array([b.shares[m] for m in b.members])
        self.di = np.array([sym_idx[m] for m in b.den_members], dtype=np.int64)
        self.dsh = np.array([b.den_shares[m] for m in b.den_members])

    def value(self, block: np.ndarray) -> np.ndarray:
        v = block[:, self.mi] @ self.sh
        if self.di.size:
            v = v / (block[:, self.di] @ self.dsh)
        return v


def evaluate(panel: Panel, shape: Shape, baskets: list[Basket], windows: list[int], fit_end: int,
             scoring: ScoringConfig, ref_window: str = "longest", min_ref: int = 0) -> list[Result]:
    """ref_window: which window describes a basket (score, metrics, channel, chart): the longest one that
    holds the shape ("longest"), or the best-scoring one that holds it and is at least ``min_ref`` bars
    long ("best")."""
    if not baskets:
        return []
    sym_idx = {s: i for i, s in enumerate(panel.symbols)}
    legs = [_Legs(b, sym_idx) for b in baskets]

    per_window: dict[int, tuple[np.ndarray, dict]] = {}
    for L in windows:
        s = fit_end - L
        if s < 0:
            continue
        block = panel.close[s:fit_end]
        with np.errstate(invalid="ignore", divide="ignore"):
            V = np.column_stack([lg.value(block) for lg in legs])
        valid = np.isfinite(V).all(axis=0) & (V > 0).all(axis=0)
        V = np.where(valid, V, 1.0)
        res = shape.score(V / V[0], scoring)
        k = np.array([b.size for b in baskets])
        sc = res.score * np.clip(1.0 - scoring.complexity_penalty * (k - 1), 0, 1)
        sc = np.where(valid, sc, 0.0)
        per_window[L] = (sc, res.metrics)

    out: list[Result] = []
    used = sorted(per_window)
    for i, b in enumerate(baskets):
        ws = {L: float(per_window[L][0][i]) for L in used}
        held = [L for L in used if ws[L] >= scoring.threshold]
        duration = max(held) if held else 0
        if held and ref_window == "best":
            eligible = [L for L in held if L >= min_ref] or [duration]
            ref = max(eligible, key=lambda L: (ws[L], L))
        else:
            ref = duration or max(ws, key=ws.get)
        metrics = {k: float(v[i]) for k, v in per_window[ref][1].items()}
        chart_start = fit_end - max(ref, b.fit_window)
        full = legs[i].value(panel.close[chart_start:])
        curve = full / full[0]
        off = fit_end - ref - chart_start
        seg = curve[off:] / curve[off]
        bounds = shape.channel(seg[:ref], scoring)
        Yh = to_space(seg[ref:], scoring.space)
        t = np.arange(ref, ref + len(Yh))
        lo, hi = bounds(t)
        if len(Yh) == 0:
            alive = True
        elif shape.direction != 0:
            # trend: holdout stays on the right side of the channel AND its worst counter-move is no worse
            # than what the basket typically did over spans of the same length inside the held window
            # (a 10y channel is wide; a -30% month inside it is still a break)
            side_ok = np.all(Yh >= lo) if shape.direction > 0 else np.all(Yh <= hi)
            Yin = to_space(seg[:ref], scoring.space)
            Yh0 = np.concatenate([Yin[-1:], Yh])
            alive = bool(side_ok and _adverse(Yh0, shape.direction) <= alive_limit(Yin, len(Yh0), shape.direction))
        else:
            alive = bool(np.all((Yh >= lo) & (Yh <= hi)))
        if shape.direction == 0:
            # where the last bar sits in the held span's band: 0 = bottom edge, 1 = top edge, outside = signal
            q = scoring.range_band_pct
            Yin = to_space(seg[:ref], scoring.space)
            blo, _, bhi = range_band(Yin, q)
            ylast = float(to_space(seg[-1:], scoring.space)[0])
            metrics["band_pos"] = (ylast - blo) / max(bhi - blo, 1e-12)
        hold_ret = float(curve[-1] / curve[fit_end - chart_start - 1] - 1.0) if len(Yh) else 0.0
        last = panel.close[-1, legs[i].mi] * legs[i].sh
        dlast = panel.close[-1, legs[i].di] * legs[i].dsh
        out.append(Result(
            basket=b, duration=duration, score=ws[ref], metrics=metrics, window_scores=ws, alive=alive,
            holdout_return=hold_ret, weights_now=[float(x) for x in last / last.sum()],
            chart_start=chart_start, curve=curve, fit_end=fit_end,
            den_weights_now=[float(x) for x in dlast / dlast.sum()] if dlast.size else [], ref_window=ref,
        ))
    return out


def _adverse(Y: np.ndarray, direction: int) -> float:
    """Worst counter-trend move of a 1-D curve: max drawdown for an uptrend, max rally for a downtrend."""
    if direction > 0:
        return float((np.maximum.accumulate(Y) - Y).max())
    return float((Y - np.minimum.accumulate(Y)).max())


def alive_limit(Y: np.ndarray, span: int, direction: int, q: float = 95.0) -> float:
    """q-th percentile of the worst counter-move over every ``span``-bar stretch of Y."""
    if len(Y) <= span:
        return _adverse(Y, direction)
    W = np.lib.stride_tricks.sliding_window_view(Y, span)
    if direction > 0:
        adv = (np.maximum.accumulate(W, axis=1) - W).max(axis=1)
    else:
        adv = (W - np.minimum.accumulate(W, axis=1)).max(axis=1)
    return float(np.percentile(adv, q))


def rank(results: list[Result], cfg: RankingConfig, by: str = "duration", min_held: int = 0) -> list[Result]:
    pool = [r for r in results
            if r.duration > 0 and r.duration >= min_held and (r.alive or not cfg.require_alive)]
    if by == "score":
        pool.sort(key=lambda r: (-r.score, -r.duration, r.basket.size, -r.basket.fit_window))
    else:
        pool.sort(key=lambda r: (-r.duration, -r.score, r.basket.size, -r.basket.fit_window))
    kept: list[Result] = []
    uses: dict[str, int] = {}
    for r in pool:
        mem = set(r.basket.all_members)
        if any(uses.get(m, 0) >= cfg.max_per_member for m in mem):
            continue
        if any(len(mem & set(k.basket.all_members)) / min(len(mem), k.basket.size) > cfg.max_overlap
               for k in kept):
            continue
        kept.append(r)
        for m in mem:
            uses[m] = uses.get(m, 0) + 1
        if len(kept) >= cfg.top_n:
            break
    return kept


__all__ = ["Result", "evaluate", "rank", "penalised"]
