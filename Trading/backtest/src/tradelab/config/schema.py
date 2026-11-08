"""Run configuration (pydantic, extra=forbid, config_version=1)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataCfg(_M):
    source: str = "synthetic"                     # yfinance|csv|parquet|databento|synthetic
    symbols: list[str]
    start: str | None = None
    end: str | None = None
    freq: str = "1d"                              # 1d | 1m | 5m | 15m | 1h ...
    base_freq: str | None = None                  # load at this freq then session-resample to `freq`
    adjusted: bool = True
    session: Literal["rth", "all"] = "rth"        # filter loaded bars to RTH or keep Globex/ETH
    options: dict[str, Any] = Field(default_factory=dict)   # source options (path, preset, seed, ...)
    instruments: dict[str, dict[str, Any]] = Field(default_factory=dict)  # per-symbol spec overrides
    cash: str | float | None = None               # symbol for risk-free (e.g. ^IRX), or constant annual rate, or None
    benchmark: str | None = None
    ffill_limit: int = 3
    align: Literal["intersection", "union"] = "intersection"
    strict_quality: bool = False
    refresh: bool = False
    continuous: Literal["none", "volume", "calendar"] = "none"
    adjust: Literal["difference", "ratio", "none"] = "difference"   # continuous back-adjustment (see docs/EXECUTION_MODEL.md)


class RiskRules(_M):
    max_trades_per_day: int | None = None
    stop_after_consecutive_losses: int | None = None
    daily_loss_limit_usd: float | None = None
    daily_loss_limit_r: float | None = None
    trade_window: tuple[str, str] | None = None   # exchange-tz "HH:MM" (decision-bar end in [start, end))
    min_decision_bar_volume: float | None = None  # volume-per-bar filter on the decision bar


class ExecCfg(_M):
    fill: Literal["next_open", "next_close", "same_close_unsafe"] = "next_open"
    allow_unsafe: bool = False
    vector_sizing: Literal["weight", "units"] = "weight"
    commission_per_contract: float | None = None  # per side; None -> instrument default
    commission_bps: float = 0.0
    slippage_ticks: float = 0.0
    slippage_bps: float = 0.0
    stop_extra_slippage_ticks: float = 0.0
    borrow_bps: float = 0.0                       # annual, on short notional (vector)
    cash_spread_bps: float = 0.0
    leverage_cap: float | None = None
    intrabar: Literal["conservative", "optimistic"] = "conservative"
    limit_fill: Literal["touch", "through"] = "through"   # resting limit orders (entries AND targets): touch = fill when price reaches the limit; through = needs one tick beyond
    flatten_at: str | None = None                 # "HH:MM" exchange tz; exit at close of first bar ending >= this
    session_flat: bool = True                     # force flat at last bar of session (event engine)
    risk: RiskRules = Field(default_factory=RiskRules)


class StrategyCfg(_M):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    path: str | None = None                       # extra strategies dir / module file
    warmup_sessions: int | None = None            # history before `start` for features (None: strategy attr, else 20 intraday / 300 daily)
    grid: dict[str, list[Any]] | Literal["auto"] | None = None   # optimize/walk-forward axes; "auto" = grid(...) hints on Params


class WalkForwardCfg(_M):
    is_len: int                                   # in-sample sessions
    oos_len: int                                  # out-of-sample sessions
    step: int | None = None                       # default oos_len (non-overlapping OOS)
    scheme: Literal["rolling", "anchored"] = "rolling"
    purge: int = 0                                # sessions dropped between IS and OOS


class RobustnessCfg(_M):
    bootstrap_n: int = 2000
    mc_n: int = 2000
    seed: int | None = None                       # default: run seed
    cost_mults: list[float] = Field(default_factory=lambda: [0.0, 1.0, 2.0, 3.0])
    cost_variants: dict[str, dict[str, Any]] | None = None   # label -> param overrides (e.g. {"slow+10": {"slow": 110}})
    objective: str = "sharpe"
    n_jobs: int = 1
    pbo_slices: int = 16
    walkforward: WalkForwardCfg | None = None     # needs strategy.grid


class AnalyticsCfg(_M):
    periods_per_year: int | None = None           # None -> top-level periods_per_year (252; 365 for crypto)


class RunConfig(_M):
    config_version: Literal[1] = 1
    name: str = "run"
    data: DataCfg
    strategy: StrategyCfg
    execution: ExecCfg = Field(default_factory=ExecCfg)
    initial_capital: float = 100_000.0
    seed: int = 0
    periods_per_year: int = 252
    causality_check: bool = True
    robustness: RobustnessCfg = Field(default_factory=RobustnessCfg)
    analytics: AnalyticsCfg = Field(default_factory=AnalyticsCfg)
