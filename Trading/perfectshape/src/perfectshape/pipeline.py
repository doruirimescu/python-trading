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
                f"ratio mode: {len(panel.symbols)} instruments at {cfg.ratio.k} vs {cfg.ratio.k} "
                f"give {n_ratios:,} ratios > ratio.max_ratios={cfg.ratio.max_ratios:,}; "
                "use a smaller universe or smaller baskets")
        log.info("ratio mode: %s ratios of %d vs %d instruments per window", f"{n_ratios:,}",
                 cfg.ratio.k, cfg.ratio.k)

    rk = cfg.ranking
    ranked: dict[str, list[Result]] = {}
    n_cand: dict[str, int] = {}

    def output(finished: bool) -> ScanOutput:
        return ScanOutput(cfg=cfg, universe=u, panel=panel, fit_end=fit_end, ranked=dict(ranked),
                          n_candidates=dict(n_cand), seconds=time.perf_counter() - t0, done=finished)

    def by_score(shape) -> bool:
        return shape.direction == 0 and rk.range_sort == "score"

    def rank_shape(shape, results: list[Result]) -> list[Result]:
        return rank(results, rk, by="score" if by_score(shape) else "duration",
                    min_held=rk.range_min_held if by_score(shape) else 0)

    shapes = [get_shape(name) for name in cfg.search.shapes]
    # evaluation of a basket depends only on the basket (members, shares, fit window), so it is cached:
    # live snapshots re-offer the same candidates many times
    cache: dict[tuple, Result] = {}

    def evaluated(shape, found: list) -> list[Result]:
        key = lambda b: (shape.name, tuple(b.members), tuple(b.den_members), b.fit_window)
        new = [b for b in found if key(b) not in cache]
        if new:
            for b, r in zip(new, evaluate(panel, shape, new, windows, fit_end, cfg.scoring,
                                          ref_window="best" if by_score(shape) else "longest",
                                          min_ref=rk.range_min_score_window)):
                cache[key(b)] = r
        return [cache[key(b)] for b in found]

    if ratio_mode:
        # window by window, longest first (long-lived shapes rank first, so the best results show up early),
        # all shapes scored from the same chunks; live snapshots of the window in progress every ~10 s
        order = sorted(windows, reverse=True)
        total = float(sum(order)) * len(shapes)
        done = 0.0
        finished: dict[str, list[Result]] = {s.name: [] for s in shapes}
        n_cand.update({s.name: 0 for s in shapes})
        ctl.stage("searching " + " + ".join(s.name for s in shapes))
        for L in order:
            detail = f"window {L} bars"
            n_full = len(panel.complete_columns(fit_end - L, panel.n_bars))
            if n_full < len(panel.symbols):
                # a stock listed for less than the window cannot be in any of its ratios
                detail += f", {n_full} of {len(panel.symbols)} stocks have the full history"
                log.info("window %d: %d of %d instruments have the full history", L, n_full, len(panel.symbols))
            ctl.checkpoint(done / total, detail)

            def on_chunk(frac, _base=done, _L=L, _d=detail):
                ctl.checkpoint((_base + frac * _L * len(shapes)) / total, _d)

            def on_snapshot(found: dict, _L=L):
                for s in shapes:
                    ranked[s.name] = rank_shape(s, finished[s.name] + evaluated(s, found[s.name]))
                ctl.partial(output(False))

            found = search_ratio_window(panel, shapes, L, fit_end, cfg.ratio, cfg.scoring,
                                        on_chunk=on_chunk, on_snapshot=on_snapshot)
            for s in shapes:
                finished[s.name] += evaluated(s, found[s.name])
                n_cand[s.name] += len(found[s.name])
                ranked[s.name] = rank_shape(s, finished[s.name])
                log.info("%s: window %d -> %d candidates, %d ranked", s.name, L, n_cand[s.name],
                         len(ranked[s.name]))
            done += L * len(shapes)
            ctl.partial(output(False))
    else:
        total = float(sum(windows)) * len(shapes)
        done = 0.0
        for shape in shapes:
            ctl.stage(f"searching {shape.name}")
            # the same members fitted on different windows get different weights: keep every variant, the
            # ranking keeps the best one (overlap filter drops the rest)
            results: list[Result] = []
            n_cand[shape.name] = 0
            for L in windows:
                ctl.checkpoint(done / total, f"{shape.name} · window {L} bars")
                found = search_window(panel, shape, L, fit_end, cfg.search, cfg.scoring)
                results += evaluated(shape, found)
                n_cand[shape.name] += len(found)
                ranked[shape.name] = rank_shape(shape, results)
                done += L
                log.info("%s: window %d -> %d candidates, %d ranked", shape.name, L, n_cand[shape.name],
                         len(ranked[shape.name]))
                ctl.partial(output(False))
    ctl.checkpoint(1.0, "done")
    return output(True)
