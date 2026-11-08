"""Run configuration (YAML -> pydantic, ``extra=forbid`` so a typo is an error)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ShapeName = Literal["uptrend", "downtrend", "range"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UniverseConfig(_Strict):
    lists: list[str] = Field(default_factory=list, description="names in universes/ or paths to .csv/.txt/.json/.yaml")
    tickers: list[str] = Field(default_factory=list, description="extra tickers added to the lists")
    exclude: list[str] = Field(default_factory=list)
    limit: Optional[int] = Field(None, ge=1, description="keep only the first N tickers (smoke runs)")

    @model_validator(mode="after")
    def _non_empty(self):
        if not self.lists and not self.tickers:
            raise ValueError("universe needs at least one of lists / tickers")
        return self


class DataConfig(_Strict):
    source: Literal["yfinance", "synthetic"] = "yfinance"
    end: Optional[date] = Field(None, description="last bar of the analysis; null = latest available")
    years: float = Field(6.0, gt=0, description="history to load (must cover the longest window + holdout)")
    cache_dir: str = "data_cache"
    max_age_days: int = Field(1, ge=0, description="re-download a cached ticker older than this (0 = always)")
    chunk_size: int = Field(100, ge=1)
    max_gap_bars: int = Field(3, ge=0, description="forward-fill holes up to this many bars")
    synthetic: dict = Field(default_factory=dict, description="options for the synthetic source (tests)")


class SearchConfig(_Strict):
    shapes: list[ShapeName] = Field(default_factory=lambda: ["uptrend", "downtrend", "range"])
    windows: list[int] = Field(
        default_factory=lambda: [63, 126, 252, 378, 504, 756, 1008, 1260],
        description="lookback ladder in bars; each one is fitted and every basket is re-scored on all of them",
    )
    holdout_bars: int = Field(21, ge=0, description="most recent bars kept out of fitting; used to check the shape is alive")
    long_only: bool = True
    max_weight: float = Field(0.7, gt=0, le=1.0, description="cap on |weight| of one instrument in a basket")
    min_weight: float = Field(0.03, ge=0, description="drop members whose |weight| ends below this")
    max_assets: int = Field(3, ge=1, le=8)
    seeds: int = Field(25, ge=1, description="greedy searches start from the best N single instruments")
    ridge: float = Field(1e-4, ge=0)
    min_improvement: float = Field(0.005, ge=0, description="stop growing a basket when the score gain is below this")

    @field_validator("windows")
    @classmethod
    def _sorted(cls, v):
        if not v or min(v) < 20:
            raise ValueError("windows must be non-empty and each >= 20 bars")
        return sorted(set(v))


class ScoringConfig(_Strict):
    space: Literal["log", "linear"] = "log"
    threshold: float = Field(0.6, ge=0, le=1, description="a window 'holds the shape' when its score >= this")
    min_annual_return: float = Field(0.10, ge=0, description="trend gate: |annualised move| must reach this")
    min_range_height: float = Field(0.08, ge=0, description="range gate: (p95-p5)/median must reach this")
    max_range_drift: float = Field(0.5, gt=0, description="range gate: drift / band height must stay below this")
    complexity_penalty: float = Field(0.02, ge=0, description="score multiplier loss per extra basket member")
    periods_per_year: int = 252


class RankingConfig(_Strict):
    top_n: int = Field(25, ge=1)
    require_alive: bool = Field(True, description="drop baskets whose holdout broke the shape")
    max_overlap: float = Field(0.67, ge=0, le=1, description="drop a basket sharing more than this share of members with a better one")
    max_per_member: int = Field(2, ge=1, description="an instrument may appear in at most this many ranked baskets")


class OutputConfig(_Strict):
    dir: str = "runs"
    html: bool = True


class RunConfig(_Strict):
    config_version: Literal[1] = 1
    name: str = "scan"
    universe: UniverseConfig
    data: DataConfig = Field(default_factory=DataConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @model_validator(mode="after")
    def _history_covers_windows(self):
        needed = max(self.search.windows) + self.search.holdout_bars
        have = int(self.data.years * self.scoring.periods_per_year)
        if have < needed:
            raise ValueError(f"data.years={self.data.years} gives ~{have} bars but windows+holdout need {needed}")
        return self


def load_config(path: str | Path) -> RunConfig:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return RunConfig.model_validate(raw)
