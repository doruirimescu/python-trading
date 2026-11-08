"""scan = universe -> panel -> per shape: search every window -> evaluate durations/holdout -> rank."""

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
from perfectshape.search import Basket, search_window
from perfectshape.shapes import get_shape
from perfectshape.universe import Universe, build_universe

log = logging.getLogger(__name__)


@dataclass
class ScanOutput:
    cfg: RunConfig
    universe: Universe
    panel: Panel
    fit_end: int
    ranked: dict[str, list[Result]]
    n_candidates: dict[str, int]
    seconds: float


def scan(cfg: RunConfig, *, panel: Optional[Panel] = None, today: Optional[date] = None) -> ScanOutput:
    t0 = time.perf_counter()
    u = build_universe(cfg.universe.lists, cfg.universe.tickers, cfg.universe.exclude, cfg.universe.limit)
    if panel is None:
        panel = load_panel(u.tickers, cfg.data, today=today)
    log.info("panel: %d bars x %d symbols (%s .. %s)", panel.n_bars, len(panel.symbols),
             panel.dates[0], panel.dates[-1])
    fit_end = panel.n_bars - cfg.search.holdout_bars
    windows = [w for w in cfg.search.windows if w <= fit_end]
    if not windows:
        raise ValueError(f"panel has {panel.n_bars} bars, too short for any window + holdout")

    ranked: dict[str, list[Result]] = {}
    n_cand: dict[str, int] = {}
    for name in cfg.search.shapes:
        shape = get_shape(name)
        # the same members fitted on different windows get different weights: keep every variant, the
        # ranking keeps the one that holds the shape longest (overlap filter drops the rest)
        found: list[Basket] = []
        for L in windows:
            found += search_window(panel, shape, L, fit_end, cfg.search, cfg.scoring)
            log.info("%s: window %d -> %d candidate baskets so far", name, L, len(found))
        results = evaluate(panel, shape, found, windows, fit_end, cfg.scoring)
        ranked[name] = rank(results, cfg.ranking)
        n_cand[name] = len(found)
        log.info("%s: %d candidates, %d ranked", name, len(found), len(ranked[name]))
    return ScanOutput(cfg=cfg, universe=u, panel=panel, fit_end=fit_end, ranked=ranked, n_candidates=n_cand,
                      seconds=time.perf_counter() - t0)
