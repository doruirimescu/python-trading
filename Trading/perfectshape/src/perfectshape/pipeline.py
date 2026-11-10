"""scan = universe -> panel -> per shape: search every window (weighted baskets or basket ratios) -> evaluate
durations/holdout -> rank.

A :class:`ScanControl` lets a caller (the dashboard) follow and steer a running scan: ``checkpoint`` is called
between chunks of work and may block (pause) or raise :class:`ScanCancelled` (stop); ``partial`` receives the
ranking so far after every window. Baskets are evaluated as soon as their window is searched (evaluation of a
basket does not depend on the others), so partial rankings are exact for the windows done so far.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

from perfectshape.config import RunConfig
from perfectshape.data.panel import Panel
from perfectshape.data.sources import load_panel
from perfectshape.evaluate import Result, evaluate, rank
from perfectshape.ratio import count_ratios, search_ratio_window
from perfectshape.search import search_window
from perfectshape.shapes import get_shape
from perfectshape.universe import Universe, build_universe

log = logging.getLogger(__name__)


class ScanCancelled(Exception):
    pass


class ScanControl:
    """No-op hooks; subclass to follow / pause / stop a scan."""

    def stage(self, text: str) -> None:
        """A coarse step started (loading data, a shape)."""

    def checkpoint(self, progress: float, detail: str = "") -> None:
        """Called between chunks of work with overall progress in [0, 1]. May block or raise ScanCancelled."""

    def partial(self, out: "ScanOutput") -> None:
        """Ranking so far (after every window)."""


@dataclass
class ScanOutput:
    cfg: RunConfig
    universe: Universe
    panel: Panel
    fit_end: int
    ranked: dict[str, list[Result]]
    n_candidates: dict[str, int]
    seconds: float
    done: bool = True


def scan(cfg: RunConfig, *, panel: Optional[Panel] = None, today: Optional[date] = None,
         control: Optional[ScanControl] = None) -> ScanOutput:
    ctl = control or ScanControl()
    t0 = time.perf_counter()
    ctl.stage("building universe")
    u = build_universe(cfg.universe.lists, cfg.universe.tickers, cfg.universe.exclude, cfg.universe.limit)
    if panel is None:
        ctl.stage(f"loading prices for {len(u.tickers)} instruments")
        panel = load_panel(u.tickers, cfg.data, today=today)
    log.info("panel: %d bars x %d symbols (%s .. %s)", panel.n_bars, len(panel.symbols),
             panel.dates[0], panel.dates[-1])
    fit_end = panel.n_bars - cfg.search.holdout_bars
    windows = [w for w in cfg.search.windows if w <= fit_end]
    if not windows:
        raise ValueError(f"panel has {panel.n_bars} bars, too short for any window + holdout")

    ratio_mode = cfg.search.mode == "ratio"
    if ratio_mode:
        n_ratios = count_ratios(len(panel.symbols), cfg.ratio)
        if n_ratios > cfg.ratio.max_ratios:
            raise ValueError(
                f"ratio mode: {len(panel.symbols)} instruments with k_num={cfg.ratio.k_num}, "
                f"k_den={cfg.ratio.k_den} give {n_ratios:,} ratios > ratio.max_ratios={cfg.ratio.max_ratios:,}; "
                "use a smaller universe or smaller baskets")
        log.info("ratio mode: %s ratios of %d vs %d instruments per window", f"{n_ratios:,}",
                 cfg.ratio.k_num, cfg.ratio.k_den)

    # work is proportional to bars x candidates, so each (shape, window) step weighs its window length
    steps = [(name, L) for name in cfg.search.shapes for L in windows]
    total = float(sum(L for _, L in steps))
    done = 0.0
    rk = cfg.ranking
    ranked: dict[str, list[Result]] = {}
    n_cand: dict[str, int] = {}

    def output(finished: bool) -> ScanOutput:
        return ScanOutput(cfg=cfg, universe=u, panel=panel, fit_end=fit_end, ranked=dict(ranked),
                          n_candidates=dict(n_cand), seconds=time.perf_counter() - t0, done=finished)

    for name in cfg.search.shapes:
        shape = get_shape(name)
        ctl.stage(f"searching {name}")
        by_score = shape.direction == 0 and rk.range_sort == "score"
        # the same members fitted on different windows get different weights: keep every variant, the
        # ranking keeps the best one (overlap filter drops the rest)
        results: list[Result] = []
        n_cand[name] = 0
        for L in windows:
            detail = f"{name} · window {L} bars"
            ctl.checkpoint(done / total, detail)
            if ratio_mode:
                def on_chunk(frac, _base=done, _L=L, _d=detail):
                    ctl.checkpoint((_base + frac * _L) / total, _d)
                found = search_ratio_window(panel, shape, L, fit_end, cfg.ratio, cfg.scoring, on_chunk=on_chunk)
            else:
                found = search_window(panel, shape, L, fit_end, cfg.search, cfg.scoring)
            results += evaluate(panel, shape, found, windows, fit_end, cfg.scoring,
                                ref_window="best" if by_score else "longest", min_ref=rk.range_min_score_window)
            n_cand[name] += len(found)
            ranked[name] = rank(results, rk, by="score" if by_score else "duration",
                                min_held=rk.range_min_held if by_score else 0)
            done += L
            log.info("%s: window %d -> %d candidates, %d ranked", name, L, n_cand[name], len(ranked[name]))
            ctl.partial(output(False))
    ctl.checkpoint(1.0, "done")
    return output(True)
