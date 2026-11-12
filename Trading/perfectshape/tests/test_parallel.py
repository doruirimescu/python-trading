"""Multi-core search: results do not depend on the number of threads."""

import threading
import time

import numpy as np
import pytest

from perfectshape.config import RunConfig
from perfectshape.parallel import n_workers, ordered_map
from perfectshape.pipeline import scan
from perfectshape.solver import Bounds, project_weights


def _ranked(out):
    return {shape: [(r.basket.members, r.basket.den_members, r.basket.weights, r.basket.fit_window,
                     r.score, r.duration, r.alive) for r in rs]
            for shape, rs in out.ranked.items()}


def _with_workers(cfg: RunConfig, workers: int) -> RunConfig:
    return cfg.model_copy(update={"search": cfg.search.model_copy(update={"workers": workers})})


def test_weighted_scan_same_on_one_or_many_threads():
    tickers = [f"S{i:02d}" for i in range(30)]
    cfg = RunConfig.model_validate({
        "universe": {"tickers": tickers},
        "data": {"source": "synthetic", "synthetic": {
            "n_bars": 1600, "seed": 3,
            "plant": {"uptrend": ["S03", "S17"], "downtrend": ["S08", "S22"], "range": ["S11", "S26"]}}},
        "search": {"windows": [126, 252, 504, 1008], "seeds": 30}})
    one, many = scan(_with_workers(cfg, 1)), scan(_with_workers(cfg, 4))
    assert _ranked(one) == _ranked(many)
    assert any(_ranked(one).values())


def test_ratio_scan_same_on_one_or_many_threads(monkeypatch):
    import perfectshape.ratio as R
    monkeypatch.setattr(R, "CHUNK_ELEMENTS", 20_000)                 # many chunks in flight at once
    cfg = RunConfig.model_validate({
        "universe": {"tickers": [f"S{i:02d}" for i in range(10)]},
        "data": {"source": "synthetic", "years": 6, "synthetic": {"n_bars": 1300, "seed": 2}},
        "search": {"mode": "ratio", "windows": [252, 504, 1008]},
        "ratio": {"keep_per_window": 20}})                          # a small top: pruning floors bind early
    one, many = scan(_with_workers(cfg, 1)), scan(_with_workers(cfg, 4))
    assert _ranked(one) == _ranked(many)
    assert any(_ranked(one).values())


def _project_row_reference(w, lo, cap):
    """The original one-row-at-a-time projection."""
    w = np.clip(w, lo, None)
    s = w.sum()
    if s <= 1e-12:
        return np.full_like(w, np.nan)
    w = w / s
    fixed = np.zeros(len(w), dtype=bool)
    for _ in range(len(w)):
        over = (w > cap + 1e-12) & ~fixed
        if not over.any():
            break
        fixed |= over
        w[fixed] = cap
        free = ~fixed
        rem = 1.0 - cap * fixed.sum()
        fs = w[free].sum()
        w[free] = w[free] * rem / fs if fs > 1e-12 else rem / max(free.sum(), 1)
    if np.any(w < lo - 1e-9) or np.any(w > cap + 1e-9):
        return np.full_like(w, np.nan)
    return w


@pytest.mark.parametrize("k", range(1, 9))
@pytest.mark.parametrize("long_only", [True, False])
@pytest.mark.parametrize("max_weight", [0.3, 0.5, 0.7, 1.0])
def test_batched_projection_matches_row_by_row_exactly(k, long_only, max_weight):
    rng = np.random.default_rng(k)
    W = rng.standard_normal((2000, k)) * rng.choice([0.1, 1, 5], (2000, 1)) + rng.choice([0, 1 / k], (2000, 1))
    W[::97] = 0.0
    W[::89, 0] = np.nan
    W[::83] = 1.0 / k
    b = Bounds(long_only=long_only, max_weight=max_weight)
    cap = b.max_weight if k * b.max_weight >= 1.0 else 1.0
    lo = 0.0 if b.long_only else -cap
    ref = W.copy()
    bad = ~np.all((W >= lo - 1e-9) & (W <= cap + 1e-9), axis=1) & ~np.isnan(W).any(axis=1)
    for r in np.flatnonzero(bad):
        ref[r] = _project_row_reference(W[r].copy(), lo, cap)
    assert np.array_equal(project_weights(W, b), ref, equal_nan=True)


def test_ordered_map_keeps_order_and_reads_items_lazily():
    made = []

    def items():
        for i in range(40):
            made.append(i)
            yield i

    def slow_square(i):
        time.sleep(0.001 * ((7 * i) % 5))                             # finish out of order
        return i * i

    out = []
    for r in ordered_map(slow_square, items(), workers=4):
        assert len(made) - len(out) <= 2 * 4                          # never more than 2 x workers ahead
        out.append(r)
    assert out == [i * i for i in range(40)]
    assert list(ordered_map(slow_square, range(5), workers=1)) == [0, 1, 4, 9, 16]
    assert n_workers(3) == 3 and n_workers(0) >= 1


def test_ordered_map_stops_on_an_error_from_the_items():
    def items():
        yield from range(5)
        raise KeyboardInterrupt("stop")                               # like ScanCancelled from a checkpoint

    with pytest.raises(KeyboardInterrupt):
        list(ordered_map(lambda i: i, items(), workers=4))


def test_ordered_map_nested_in_a_worker_runs_inline():
    def inner(i):
        names = set(ordered_map(lambda j: threading.current_thread().name, range(3), workers=4))
        return names, threading.current_thread().name

    for names, worker in ordered_map(inner, range(4), workers=4):
        assert names == {worker}                                      # no second pool level, no deadlock
