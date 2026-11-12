"""Basket-ratio search (``search.mode: ratio``) for one shape over one fit window.

Same object as Trading/basket (mrscore ``RatioUniverse``): every price is normalised to 1.0 at the window
start, a basket is the equal-weight mean of its members, and a ratio is ``basket(num) / basket(den)``.
Baskets are symmetric (k vs k). Every unordered pair of disjoint k-baskets is enumerated in chunks (never
all at once) and scored with the shape; the best ``keep_per_window`` go on to evaluation (duration ladder +
holdout, see evaluate.py), exactly like the weighted baskets.

Speed (log scoring space, the default): each basket's log curve is computed once per window, so a ratio is
one subtraction, log(A / B) = log A - log B, and the shape scores it directly (``Shape.score_y``).

Orientation: a falling A/B is a rising B/A. For trends the ratio is flipped when its fitted slope is
negative (log(B / A) = -log(A / B)) and scored once, so every trend is reported as "numerator outperforms
denominator"; the other orientation would score 0 anyway (wrong direction). A range has no direction.
"""

from __future__ import annotations

import time
from itertools import combinations
from math import comb
from typing import Callable, Optional

import numpy as np

from perfectshape.config import RatioConfig, ScoringConfig
from perfectshape.data.panel import Panel
from perfectshape.parallel import n_workers, ordered_map
from perfectshape.search import Basket, penalised
from perfectshape.shapes import Shape, _centered_tau

CHUNK_ELEMENTS = 4_000_000          # bars x ratios scored per vectorised call (one thread)
PARALLEL_CHUNK_ELEMENTS = 1_000_000  # the same with several threads: smaller chunks, less memory per thread
FLOAT32_ABOVE_BYTES = 2_000_000_000  # basket curves are kept in float32 when float64 would exceed this


def count_ratios(n: int, cfg: RatioConfig) -> int:
    """Number of unordered basket pairs (ratios) scanned for n instruments at k vs k."""
    k = cfg.k
    if k > n:
        return 0
    if cfg.allow_overlap:
        return comb(comb(n, k), 2)
    if 2 * k > n:
        return 0
    return comb(n, k) * comb(n - k, k) // 2


def _library(n: int, k: int) -> np.ndarray:
    return np.array(list(combinations(range(n), k)), dtype=np.int32).reshape(-1, k)


def _pair_chunks(b: int, chunk: int):
    """Yield (I, J) index arrays over basket pairs i < j, about ``chunk`` pairs at a time."""
    i = 0
    while i < b - 1:
        Is, Js, size = [], [], 0
        while i < b - 1 and size < chunk:
            Is.append(np.full(b - i - 1, i, dtype=np.int64))
            Js.append(np.arange(i + 1, b, dtype=np.int64))
            size += b - i - 1
            i += 1
        yield np.concatenate(Is), np.concatenate(Js)


def _overlap_fn(lib: np.ndarray, n: int):
    """Vectorised 'do baskets I and J share an instrument?': 64-bit masks when n <= 64, else boolean rows."""
    if n <= 64:
        masks = (np.uint64(1) << lib.astype(np.uint64)).sum(axis=1, dtype=np.uint64)  # distinct bits: sum == or
        return lambda I, J: (masks[I] & masks[J]) != 0
    mem = np.zeros((len(lib), n), dtype=bool)
    mem[np.arange(len(lib))[:, None], lib] = True
    return lambda I, J: (mem[I] & mem[J]).any(axis=1)


class _Top:
    """The best ``keep`` (score, numerator id, denominator id) of one shape, kept as flat arrays."""

    def __init__(self, keep: int):
        self.keep = keep
        self.s = np.empty(0)
        self.n = np.empty(0, dtype=np.int64)
        self.d = np.empty(0, dtype=np.int64)

    def floor(self) -> float:
        """Score a ratio must beat to enter the current top ``keep`` (0 until it is full)."""
        if len(self.s) < self.keep:
            return 0.0
        return float(np.partition(self.s, len(self.s) - self.keep)[len(self.s) - self.keep])

    def add(self, sc: np.ndarray, I: np.ndarray, J: np.ndarray) -> None:
        good = sc > 0
        self.s, self.n, self.d = np.r_[self.s, sc[good]], np.r_[self.n, I[good]], np.r_[self.d, J[good]]
        if len(self.s) > 4 * self.keep:
            top = np.argpartition(-self.s, self.keep)[:self.keep]
            self.s, self.n, self.d = self.s[top], self.n[top], self.d[top]

    def best(self, limit: int):
        order = np.argsort(-self.s)[:limit]
        return [(float(self.s[o]), int(self.n[o]), int(self.d[o])) for o in order]


def search_ratio_window(panel: Panel, shape: "Shape | list[Shape]", window: int, fit_end: int, rcfg: RatioConfig,
                        scoring: ScoringConfig, on_chunk: Optional[Callable[[float], None]] = None,
                        on_snapshot: Optional[Callable[[dict], None]] = None, snapshot_every: float = 10.0,
                        snapshot_size: int = 100, snapshot_first: float = 3.0, workers: int = 0):
    """Search one window for one shape (returns its baskets) or for several (a list -> {name: baskets}).

    All shapes are scored from the same chunk of ratios (built once). ``on_chunk(fraction_done)`` is called
    before every chunk (progress, pause / stop hook); ``on_snapshot({name: baskets})`` every
    ``snapshot_every`` seconds (the first after ``snapshot_first``) with each shape's ``snapshot_size`` best
    so far (live results). Chunks are scored on ``workers`` threads (0 = every logical core); the callbacks
    and the top lists stay in the calling thread, and chunks are merged in order, so the result does not
    depend on the number of threads.
    """
    single = not isinstance(shape, (list, tuple))
    shapes = [shape] if single else list(shape)
    # ranges first: trends orient (negate) the shared chunk in place
    shapes.sort(key=lambda s: s.direction != 0)
    empty = [] if single else {s.name: [] for s in shapes}
    start = fit_end - window
    if start < 0:
        return empty
    cols = panel.complete_columns(start, panel.n_bars)   # also complete through the holdout
    n = len(cols)
    if count_ratios(n, rcfg) == 0:
        return empty
    P = panel.close[start:fit_end, cols]
    X = P / P[0]
    T = X.shape[0]
    k = rcfg.k
    lib = _library(n, k)
    dtype = np.float32 if len(lib) * T * 8 > FLOAT32_ABOVE_BYTES else np.float64
    V = X[:, lib].mean(axis=2).astype(dtype, copy=False)          # (T, B) equal-weight basket values
    log_space = scoring.space == "log"
    if log_space:
        V = np.log(V)                                              # basket log curves, computed once
    overlaps = None if rcfg.allow_overlap else _overlap_fn(lib, n)
    VT = np.ascontiguousarray(V.T)                                 # (B, T): gathering ratios reads whole rows
    _, tc, _ = _centered_tau(T)
    tc = tc.astype(dtype)

    penalty = float(penalised(np.ones(1), 2 * k, scoring)[0])
    tops = {s.name: _Top(rcfg.keep_per_window) for s in shapes}

    def baskets(name: str, limit: int) -> list[Basket]:
        return [_basket(panel, name, cols, lib[i], lib[j], window, start, sc)
                for sc, i, j in tops[name].best(limit)]

    workers = n_workers(workers)
    chunk = max(1, (CHUNK_ELEMENTS if workers == 1 else min(CHUNK_ELEMENTS, PARALLEL_CHUNK_ELEMENTS)) // T)
    raw_total = len(lib) * (len(lib) - 1) // 2
    raw_done = 0
    next_snap = time.monotonic() + min(snapshot_first, snapshot_every)

    def tasks():
        """Chunks of disjoint pairs, made in the calling thread (progress, pause / stop)."""
        nonlocal raw_done
        for I, J in _pair_chunks(len(lib), chunk):
            if on_chunk is not None:
                on_chunk(raw_done / max(raw_total, 1))
            raw_done += len(I)
            if overlaps is not None:
                ok = ~overlaps(I, J)
                I, J = I[ok], J[ok]
                if len(I) == 0:
                    continue
            # exact pruning: once a top is full, a ratio must beat its weakest member to matter. A floor read
            # before earlier chunks are merged is lower, so it only prunes less: the top comes out the same
            floors = {s.name: tops[s.name].floor() / penalty if penalty > 0 else 0.0 for s in shapes}
            yield I, J, floors

    def score_chunk(task) -> list:
        """(shape name, scores, numerator ids, denominator ids) of one chunk, for every shape."""
        I, J, floors = task
        scored = []
        if log_space:
            Y = (VT[I] - VT[J]).T                                  # log(A / B), shared by the shapes
            for s in shapes:
                Is, Js = I, J
                if s.direction != 0:
                    # orient every ratio along its trend: flip (B / A) where the fitted slope is negative
                    flip = (tc @ Y) * s.direction < 0
                    Y[:, flip] *= -1
                    Is, Js = np.where(flip, J, I), np.where(flip, I, J)
                sc = s.score_y(Y, scoring, full=False, floor=floors[s.name]).score * penalty
                scored.append((s.name, sc, Is, Js))
        else:
            R = V[:, I] / V[:, J]
            for s in shapes:
                sc = s.score(R, scoring, full=False).score * penalty
                Is, Js = I, J
                if s.direction != 0:
                    sc_f = s.score(1.0 / R, scoring, full=False).score * penalty
                    flip = sc_f > sc
                    sc = np.where(flip, sc_f, sc)
                    Is, Js = np.where(flip, J, I), np.where(flip, I, J)
                scored.append((s.name, sc, Is, Js))
        return scored

    for scored in ordered_map(score_chunk, tasks(), workers):
        for name, sc, Is, Js in scored:
            tops[name].add(sc, Is, Js)
        # snapshots right after a merge, while the next chunks are being scored
        if on_snapshot is not None and time.monotonic() >= next_snap:
            on_snapshot({s.name: baskets(s.name, snapshot_size) for s in shapes})
            next_snap = time.monotonic() + snapshot_every

    out = {s.name: baskets(s.name, rcfg.keep_per_window) for s in shapes}
    return out[shapes[0].name] if single else out


def _basket(panel: Panel, shape: str, cols: np.ndarray, num: np.ndarray, den: np.ndarray, window: int,
            start: int, score: float) -> Basket:
    def leg(idx):
        syms = [panel.symbols[cols[i]] for i in idx]
        w = 1.0 / len(idx)
        return syms, [w] * len(idx), {s: w / panel.close[start, cols[i]] for s, i in zip(syms, idx)}

    m, w, sh = leg(num)
    dm, dw, dsh = leg(den)
    return Basket(shape=shape, members=m, weights=w, fit_window=window, fit_start=start, fit_score=score,
                  shares=sh, den_members=dm, den_weights=dw, den_shares=dsh)
