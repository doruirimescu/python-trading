"""Duration and holdout evaluation of found baskets, and the final ranking.

A basket is held as fixed shares (bought with its fit-window weights). Its value curve is re-scored on every
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
from perfectshape.shapes import Shape, to_space


@dataclass
class Result:
    basket: Basket
    duration: int
    score: float                                   # at the duration window (or best window if duration 0)
    metrics: dict[str, float]
    window_scores: dict[int, float]
    alive: bool
    holdout_return: float
    weights_now: list[float]
    chart_start: int                               # panel row where the chart curve starts
    curve: np.ndarray = field(repr=False, default=None)  # value from chart_start to the last bar, starts at 1.0
    fit_end: int = 0


def evaluate(panel: Panel, shape: Shape, baskets: list[Basket], windows: list[int], fit_end: int,
             scoring: ScoringConfig) -> list[Result]:
    if not baskets:
        return []
    sym_idx = {s: i for i, s in enumerate(panel.symbols)}
    members = [np.array([sym_idx[m] for m in b.members]) for b in baskets]
    shares = [np.array([b.shares[m] for m in b.members]) for b in baskets]

    per_window: dict[int, tuple[np.ndarray, dict]] = {}
    for L in windows:
        s = fit_end - L
        if s < 0:
            continue
        block = panel.close[s:fit_end]
        V = np.column_stack([block[:, mi] @ sh for mi, sh in zip(members, shares)])
        valid = np.isfinite(V).all(axis=0) & (V > 0).all(axis=0)
        V = np.where(valid, V, 1.0)
        res = shape.score(V / V[0], scoring)
        k = np.array([len(b.members) for b in baskets])
        sc = res.score * np.clip(1.0 - scoring.complexity_penalty * (k - 1), 0, 1)
        sc = np.where(valid, sc, 0.0)
        per_window[L] = (sc, res.metrics)

    out: list[Result] = []
    used = sorted(per_window)
    for i, b in enumerate(baskets):
        ws = {L: float(per_window[L][0][i]) for L in used}
        held = [L for L in used if ws[L] >= scoring.threshold]
        duration = max(held) if held else 0
        ref = duration or max(ws, key=ws.get)
        metrics = {k: float(v[i]) for k, v in per_window[ref][1].items()}
        chart_start = fit_end - max(ref, b.fit_window)
        full = panel.close[chart_start:, members[i]] @ shares[i]
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
        hold_ret = float(curve[-1] / curve[fit_end - chart_start - 1] - 1.0) if len(Yh) else 0.0
        last = panel.close[-1, members[i]] * shares[i]
        out.append(Result(
            basket=b, duration=duration, score=ws[ref], metrics=metrics, window_scores=ws, alive=alive,
            holdout_return=hold_ret, weights_now=[float(x) for x in last / last.sum()],
            chart_start=chart_start, curve=curve, fit_end=fit_end,
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


def rank(results: list[Result], cfg: RankingConfig) -> list[Result]:
    pool = [r for r in results if r.duration > 0 and (r.alive or not cfg.require_alive)]
    pool.sort(key=lambda r: (-r.duration, -r.score, len(r.basket.members), -r.basket.fit_window))
    kept: list[Result] = []
    uses: dict[str, int] = {}
    for r in pool:
        mem = set(r.basket.members)
        if any(uses.get(m, 0) >= cfg.max_per_member for m in mem):
            continue
        if any(len(mem & set(k.basket.members)) / min(len(mem), len(k.basket.members)) > cfg.max_overlap
               for k in kept):
            continue
        kept.append(r)
        for m in mem:
            uses[m] = uses.get(m, 0) + 1
        if len(kept) >= cfg.top_n:
            break
    return kept


__all__ = ["Result", "evaluate", "rank", "penalised"]
