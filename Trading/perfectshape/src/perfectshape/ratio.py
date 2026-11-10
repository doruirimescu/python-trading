"""Basket-ratio search (``search.mode: ratio``) for one shape over one fit window.

Same object as Trading/basket (mrscore ``RatioUniverse``): every price is normalised to 1.0 at the window
start, a basket is the equal-weight mean of its members, and a ratio is ``basket(num) / basket(den)``.
Every ratio of ``k_num`` vs ``k_den`` instruments is enumerated (pairs of baskets, without materialising
all ratios at once) and scored with the shape in vectorised chunks; the best ``keep_per_window`` go on to
evaluation (duration ladder + holdout, see evaluate.py), exactly like the weighted baskets.

Orientation: a falling A/B is a rising B/A. Trend shapes score both orientations of every pair and keep
the better one, so every trend is reported as "numerator outperforms denominator". A range has no
direction, so only one orientation is scored.
"""

from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Callable, Optional

import numpy as np

from perfectshape.config import RatioConfig, ScoringConfig
from perfectshape.data.panel import Panel
from perfectshape.search import Basket, penalised
from perfectshape.shapes import Shape

CHUNK_ELEMENTS = 4_000_000          # bars x ratios scored per vectorised call


def count_ratios(n: int, cfg: RatioConfig) -> int:
    """Number of baskets pairs scanned for n instruments (one orientation)."""
    kn, kd = cfg.k_num, cfg.k_den
    if kn > n or kd > n:
        return 0
    if cfg.allow_overlap:
        bn, bd = comb(n, kn), comb(n, kd)
        return comb(bn, 2) if kn == kd else bn * bd
    if kn + kd > n:
        return 0
    total = comb(n, kn) * comb(n - kn, kd)
    return total // 2 if kn == kd else total


def _library(n: int, k: int) -> np.ndarray:
    return np.array(list(combinations(range(n), k)), dtype=np.int32).reshape(-1, k)


def _pair_chunks(bn: int, bd: int, same: bool, chunk: int):
    """Yield (I, J) index arrays over basket pairs: i < j when both legs share a library, else all (i, j)."""
    i = 0
    while i < bn:
        Is, Js, size = [], [], 0
        while i < bn and size < chunk:
            j0 = i + 1 if same else 0
            if bd > j0:
                Is.append(np.full(bd - j0, i, dtype=np.int64))
                Js.append(np.arange(j0, bd, dtype=np.int64))
                size += bd - j0
            i += 1
        if Is:
            yield np.concatenate(Is), np.concatenate(Js)


def search_ratio_window(panel: Panel, shape: Shape, window: int, fit_end: int, rcfg: RatioConfig,
                        scoring: ScoringConfig, on_chunk: Optional[Callable[[float], None]] = None) -> list[Basket]:
    """``on_chunk(fraction_done)`` is called after every scored chunk (progress, pause / stop hook)."""
    start = fit_end - window
    if start < 0:
        return []
    cols = panel.complete_columns(start, panel.n_bars)   # also complete through the holdout
    n = len(cols)
    if count_ratios(n, rcfg) == 0:
        return []
    P = panel.close[start:fit_end, cols]
    X = P / P[0]
    T = X.shape[0]
    same = rcfg.k_num == rcfg.k_den
    lib_n = _library(n, rcfg.k_num)
    lib_d = lib_n if same else _library(n, rcfg.k_den)
    VN = X[:, lib_n].mean(axis=2)                          # (T, Bn) equal-weight basket values
    VD = VN if same else X[:, lib_d].mean(axis=2)
    mem_n = np.zeros((len(lib_n), n), dtype=bool)
    mem_n[np.arange(len(lib_n))[:, None], lib_n] = True
    mem_d = mem_n if same else np.zeros((len(lib_d), n), dtype=bool)
    if not same:
        mem_d[np.arange(len(lib_d))[:, None], lib_d] = True

    k = rcfg.k_num + rcfg.k_den
    keep = rcfg.keep_per_window
    best_s = np.empty(0)
    best_n = np.empty(0, dtype=np.int64)    # numerator basket id
    best_d = np.empty(0, dtype=np.int64)    # denominator basket id
    best_flip = np.empty(0, dtype=bool)     # True: numerator comes from lib_d, denominator from lib_n
    chunk = max(1, CHUNK_ELEMENTS // T)
    raw_total = len(lib_n) * (len(lib_n) - 1) // 2 if same else len(lib_n) * len(lib_d)
    raw_done = 0
    for I, J in _pair_chunks(len(lib_n), len(lib_d), same, chunk):
        raw_done += len(I)
        if on_chunk is not None:
            on_chunk(raw_done / max(raw_total, 1))
        if not rcfg.allow_overlap:
            ok = ~(mem_n[I] & mem_d[J]).any(axis=1)
            I, J = I[ok], J[ok]
            if len(I) == 0:
                continue
        R = VN[:, I] / VD[:, J]
        sc = penalised(shape.score(R, scoring).score, k, scoring)
        flip = np.zeros(len(I), dtype=bool)
        if shape.direction != 0:
            sc_f = penalised(shape.score(1.0 / R, scoring).score, k, scoring)
            flip = sc_f > sc
            sc = np.where(flip, sc_f, sc)
        good = sc > 0
        best_s = np.r_[best_s, sc[good]]
        best_n = np.r_[best_n, I[good]]
        best_d = np.r_[best_d, J[good]]
        best_flip = np.r_[best_flip, flip[good]]
        if len(best_s) > 4 * keep:
            top = np.argpartition(-best_s, keep)[:keep]
            best_s, best_n, best_d, best_flip = best_s[top], best_n[top], best_d[top], best_flip[top]

    order = np.argsort(-best_s)[:keep]
    out = []
    for o in order:
        num, den = lib_n[best_n[o]], lib_d[best_d[o]]
        if best_flip[o]:
            num, den = den, num
        out.append(_basket(panel, shape.name, cols, num, den, window, start, float(best_s[o])))
    return out


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
