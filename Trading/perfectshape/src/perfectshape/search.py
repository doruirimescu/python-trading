"""Basket search for one shape over one fit window.

1. Singles: every instrument complete over the window is scored on its own (one vectorised pass).
2. Greedy growth: from each of the best ``seeds`` singles, repeatedly add the instrument whose addition
   (with re-solved weights) scores best, until ``max_assets`` or the gain drops below ``min_improvement``.
   All candidates of a step are solved and scored in one batched call.
3. Members below ``min_weight`` are pruned and the weights re-solved.

The greedy searches of the seeds are independent and run on ``search.workers`` threads (0 = every logical
core); they are recorded in seed order, so the result does not depend on the number of threads.

Fit windows end ``holdout_bars`` before the last bar, so the most recent bars are never used to choose
members or weights (see evaluate.py for how they are used).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from perfectshape.config import ScoringConfig, SearchConfig
from perfectshape.data.panel import Panel
from perfectshape.parallel import n_workers, ordered_map
from perfectshape.shapes import Shape
from perfectshape.solver import Bounds, Solver


@dataclass
class Basket:
    shape: str
    members: list[str]
    weights: list[float]          # capital weights at the fit-window start, sum 1
    fit_window: int               # bars
    fit_start: int                # panel row of the fit-window start
    fit_score: float
    shares: dict[str, float] = field(default_factory=dict)   # units per 1.0 of capital (fixed-share holding)
    # ratio mode: the basket's value is (members @ shares) / (den_members @ den_shares); both legs start at 1.0
    den_members: list[str] = field(default_factory=list)
    den_weights: list[float] = field(default_factory=list)
    den_shares: dict[str, float] = field(default_factory=dict)

    @property
    def is_ratio(self) -> bool:
        return bool(self.den_members)

    @property
    def all_members(self) -> list[str]:
        return self.members + self.den_members

    @property
    def size(self) -> int:
        return len(self.members) + len(self.den_members)

    def key(self) -> tuple:
        return frozenset(self.members), frozenset(self.den_members)


def penalised(score: np.ndarray, k: int, cfg: ScoringConfig) -> np.ndarray:
    return score * max(0.0, 1.0 - cfg.complexity_penalty * (k - 1))


def search_window(panel: Panel, shape: Shape, window: int, fit_end: int, search: SearchConfig,
                  scoring: ScoringConfig) -> list[Basket]:
    start = fit_end - window
    if start < 0:
        return []
    cols = panel.complete_columns(start, panel.n_bars)   # also complete through the holdout
    if len(cols) == 0:
        return []
    P = panel.close[start:fit_end, cols]
    X = P / P[0]
    solver = Solver(X, shape.objective, shape.direction, search.ridge)
    bounds = Bounds(long_only=search.long_only, max_weight=search.max_weight)

    singles = shape.score(X, scoring)
    order = np.lexsort((-singles.soft, -singles.score))
    seeds = [int(i) for i in order[: search.seeds] if singles.soft[i] > 0]

    found: dict[frozenset, Basket] = {}

    def record(idx: list[int], w: np.ndarray, score: float) -> None:
        members = [panel.symbols[cols[i]] for i in idx]
        b = Basket(shape=shape.name, members=members, weights=[float(x) for x in w], fit_window=window,
                   fit_start=start, fit_score=float(score))
        b.shares = {m: float(wi / panel.close[start, cols[i]]) for m, wi, i in zip(members, w, idx)}
        prev = found.get(b.key())
        if prev is None or prev.fit_score < b.fit_score:
            found[b.key()] = b

    for i in np.flatnonzero(singles.score > 0):
        record([int(i)], np.array([1.0]), singles.score[i])

    all_idx = np.arange(len(cols))

    def grow(s: int):
        basket, w, best = [s], np.array([1.0]), float(singles.score[s])
        best_soft = float(singles.soft[s])
        while len(basket) < search.max_assets:
            cand = np.setdiff1d(all_idx, basket, assume_unique=True)
            W = solver.solve(basket, cand, bounds)
            sets = np.column_stack([np.broadcast_to(basket, (len(cand), len(basket))), cand])
            res = shape.score(solver.curves(sets, W), scoring)
            k = len(basket) + 1
            sc = np.where(np.isnan(W).any(axis=1), 0.0, penalised(res.score, k, scoring))
            soft = np.where(np.isnan(W).any(axis=1), 0.0, penalised(res.soft, k, scoring))
            j = int(np.argmax(sc)) if sc.max() > 0 else int(np.argmax(soft))
            gain = sc[j] - best if (sc[j] > 0 or best > 0) else soft[j] - best_soft
            if gain < search.min_improvement:
                break
            basket, w, best, best_soft = list(sets[j]), W[j], float(sc[j]), float(soft[j])
        return _prune(solver, shape, scoring, bounds, basket, w, best, search.min_weight)

    for basket, w, best in ordered_map(grow, seeds, n_workers(search.workers)):
        if best > 0:
            record(basket, w, best)
    return list(found.values())


def _prune(solver, shape, scoring, bounds, basket, w, best, min_weight):
    keep = np.abs(w) >= min_weight
    if keep.all() or keep.sum() == 0:
        return basket, w, best
    idx = np.asarray(basket)[keep][None, :]
    W = solver.solve_sets(idx, bounds)
    if np.isnan(W).any():
        return basket, w, best
    res = shape.score(solver.curves(idx, W), scoring)
    return list(idx[0]), W[0], float(penalised(res.score, idx.shape[1], scoring)[0])
