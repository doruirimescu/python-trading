"""Glue: config -> panel -> strategy -> engine -> RunResult; plus make_run_fn for robustness."""
from __future__ import annotations

import pandas as pd

from ..config.loader import resolved_dict
from ..config.schema import RunConfig
from ..data.calendar import is_daily
from ..data.panel import Panel, load_panel
from ..strategy.base import Strategy, features_to_arrays
from ..strategy.registry import get_strategy
from ..util.hashing import stable_hash
from .event import run_event
from .result import RunResult
from .vector import run_vector


def build_strategy(cfg: RunConfig, params: dict | None = None) -> Strategy:
    extra = [cfg.strategy.path] if cfg.strategy.path else None
    cls = get_strategy(cfg.strategy.name, extra)
    merged = {**cfg.strategy.params, **(params or {})}
    return cls(cls.Params(**merged))


def config_hash(cfg: RunConfig) -> str:
    return stable_hash(resolved_dict(cfg), 16)


def run_strategy(strategy: Strategy, panel: Panel, cfg: RunConfig, *, cost_mult: float = 1.0) -> RunResult:
    meta = {
        "strategy": strategy.name, "params": strategy.params.model_dump(), "config_hash": config_hash(cfg),
        "data_fingerprint": panel.meta.get("fingerprint") or panel.fingerprint(), "freq": panel.freq,
        "mode": strategy.mode, "seed": cfg.seed, "symbols": panel.symbols,
        "periods_per_year": cfg.periods_per_year, "name": cfg.name,
    }
    if strategy.mode == "vector":
        return run_vector(panel, strategy, cfg.execution, cfg.initial_capital, cost_mult=cost_mult, meta=meta)
    return run_event(panel, strategy, cfg.execution, cfg.initial_capital, cost_mult=cost_mult, meta=meta)


def run_backtest(cfg: RunConfig, panel: Panel | None = None, params: dict | None = None, *, cost_mult: float = 1.0):
    panel = panel if panel is not None else load_panel(cfg.data)
    strat = build_strategy(cfg, params)
    return run_strategy(strat, panel, cfg, cost_mult=cost_mult), panel, strat


DEFAULT_WARMUP_INTRADAY = 20     # sessions
DEFAULT_WARMUP_DAILY = 300       # sessions (= bars)


def warmup_sessions_for(cfg: RunConfig, strategy: Strategy | None = None) -> int:
    """Warm-up length in sessions: config > strategy attr `warmup_sessions` > 300 (daily) / 20 (intraday)."""
    if cfg.strategy.warmup_sessions is not None:
        return int(cfg.strategy.warmup_sessions)
    w = getattr(strategy, "warmup_sessions", None) if strategy is not None else None
    if w is not None:
        return int(w)
    return DEFAULT_WARMUP_DAILY if is_daily(cfg.data.freq) else DEFAULT_WARMUP_INTRADAY


class WarmupStrategy:
    """Wraps a strategy so features/signals are computed on an extended panel (with warm-up history) while the
    engine only trades the requested window. Positions are therefore flat at the window start."""

    def __init__(self, inner: Strategy, full: Panel):
        self.inner, self.full = inner, full
        self.name, self.mode, self.params, self.Params = inner.name, inner.mode, inner.params, inner.Params
        self.description = inner.description

    def _pos(self, data: Panel):
        return self.full.index.get_indexer(data.index)

    def signals(self, data: Panel):
        sig = self.inner.signals(self.full)
        return sig.reindex(data.index)

    def prepare(self, data: Panel):
        fidx = self.full.bars[self.full.primary].index
        feats = features_to_arrays(self.inner.prepare(self.full), fidx)
        pos = fidx.get_indexer(data.bars[data.primary].index)
        return {k: v[pos] for k, v in feats.items()}

    def on_bar(self, ctx):
        return self.inner.on_bar(ctx)

    def on_fill(self, ctx, fill):
        return self.inner.on_fill(ctx, fill)


def _warm_slice(panel: Panel, start, end, n_warm: int) -> Panel:
    """Panel from `n_warm` sessions before `start` through `end` (all sessions if there are fewer)."""
    if start is None or n_warm <= 0:
        return panel.slice_sessions(None, end)
    sd = pd.DatetimeIndex(sorted(panel.session_dates().dropna().unique()))
    before = sd[sd < pd.Timestamp(start)]
    ws = before[-n_warm] if len(before) >= n_warm else (before[0] if len(before) else None)
    return panel.slice_sessions(ws, end)


class RunFn:
    """Picklable run_fn(params, *, start=None, end=None, cost_mult=1.0) -> RunResult.

    - `start`/`end`: inclusive tz-naive session dates. Features/signals see `warmup_sessions` of history before
      `start`; trading, P&L, equity, trades and returns_daily only cover [start, end].
    - Intraday: flat at window start (no overnight). Daily vector strategies may enter at the first bar of the window.
    - `cost_mult` scales commissions, slippage and borrow.
    - `reload_in_worker=True` drops the panel when pickled (process-pool workers reload it from cfg.data).
    """

    def __init__(self, cfg: RunConfig, panel: Panel | None = None, *, reload_in_worker: bool = False):
        self.cfg, self.panel, self.reload_in_worker = cfg, panel, reload_in_worker

    def __getstate__(self):
        d = dict(self.__dict__)
        if self.reload_in_worker:
            d["panel"] = None
        return d

    def __call__(self, params: dict | None = None, *, start=None, end=None, cost_mult: float = 1.0) -> RunResult:
        if self.panel is None:
            self.panel = load_panel(self.cfg.data)
        strat = build_strategy(self.cfg, params)
        if start is None and end is None:
            return run_strategy(strat, self.panel, self.cfg, cost_mult=cost_mult)
        start = None if start is None else pd.Timestamp(start).tz_localize(None).normalize()
        end = None if end is None else pd.Timestamp(end).tz_localize(None).normalize()
        window = self.panel.slice_sessions(start, end)
        full = _warm_slice(self.panel, start, end, warmup_sessions_for(self.cfg, strat))
        return run_strategy(WarmupStrategy(strat, full), window, self.cfg, cost_mult=cost_mult)


def make_run_fn(cfg: RunConfig, panel: Panel | None = None, *, reload_in_worker: bool = False) -> RunFn:
    return RunFn(cfg, panel, reload_in_worker=reload_in_worker)
