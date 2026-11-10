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
    mode: Literal["weighted", "ratio"] = Field(
        "weighted",
        description="weighted: long-only baskets with solved weights; ratio: equal-weight basket A / basket B (see ratio:)",
    )
    shapes: Optional[list[ShapeName]] = Field(
        None, description="default: [uptrend, downtrend, range] (weighted) or [uptrend, range] (ratio)")
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
    range_band_pct: float = Field(
        10.0, ge=1, le=40, description="range band = median +- the smaller half of the [p, 100-p] percentile band "
                                       "(symmetric, so a one-sided spike cannot widen it)")
    range_pain_scale: float = Field(
        2.0, gt=0, description="range: penalise the worst move against an open band trade beyond 1 half-band: "
                               "score factor exp(-max(0, pain - 1) / this), pain in half-bands")
    range_segments: int = Field(
        4, ge=1, le=20, description="repeatability: the window is split into this many parts; the share of parts "
                                    "with a completed band trade multiplies into the range score")
    range_exit: Literal["mid", "opposite"] = Field(
        "mid", description="range trade: enter outside the band, exit at the median (mid) or the opposite edge")
    range_harvest_scale: float = Field(
        0.15, gt=0, description="annual range capture (log) at which the harvest term reaches 63%; higher = stricter")
    complexity_penalty: float = Field(0.02, ge=0, description="score multiplier loss per extra basket member")
    periods_per_year: int = 252


class RatioConfig(_Strict):
    """Basket-ratio search (search.mode: ratio), after Trading/basket (mrscore) RatioUniverse:
    ratio = mean(normalised prices of the numerator basket) / mean(... of the denominator basket).
    Baskets are symmetric: k instruments on each side (k vs k)."""

    k: int = Field(2, ge=1, le=8, description="instruments in each basket (k vs k)")
    allow_overlap: bool = Field(False, description="allow an instrument in both legs")
    max_ratios: int = Field(25_000_000, ge=1, description="refuse to scan more ratios than this per window")
    keep_per_window: int = Field(300, ge=1, description="best ratios per window passed on to evaluation")

    @model_validator(mode="before")
    @classmethod
    def _legacy_k(cls, data):
        """Older configs say k_num / k_den; they are accepted when equal."""
        if isinstance(data, dict) and ("k_num" in data or "k_den" in data):
            data = dict(data)
            kn, kd = data.pop("k_num", None), data.pop("k_den", None)
            ks = {x for x in (kn, kd, data.get("k")) if x is not None}
            if len(ks) > 1:
                raise ValueError(f"baskets are symmetric (k vs k); got k_num={kn}, k_den={kd}: use ratio.k")
            data["k"] = ks.pop()
        return data


class RankingConfig(_Strict):
    top_n: int = Field(25, ge=1)
    require_alive: bool = Field(True, description="drop baskets whose holdout broke the shape")
    max_overlap: float = Field(0.67, ge=0, le=1, description="drop a basket sharing more than this share of members with a better one")
    max_per_member: int = Field(2, ge=1, description="an instrument may appear in at most this many ranked baskets")
    range_sort: Literal["score", "duration"] = Field(
        "score", description="ranges: rank by score (harvest x flatness) on their best held window, or by duration "
                             "first like trends")
    range_min_held: int = Field(504, ge=0, description="ranges (range_sort: score): must have held at least this many bars")
    range_min_score_window: int = Field(
        252, ge=0, description="ranges (range_sort: score): the best-scoring window is chosen among held windows "
                               "at least this long (short in-sample bands overstate harvest)")


class OutputConfig(_Strict):
    dir: str = "runs"
    html: bool = True


class RunConfig(_Strict):
    config_version: Literal[1] = 1
    name: str = "scan"
    universe: UniverseConfig
    data: DataConfig = Field(default_factory=DataConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    ratio: RatioConfig = Field(default_factory=RatioConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @model_validator(mode="after")
    def _shapes_for_mode(self):
        ratio = self.search.mode == "ratio"
        if self.search.shapes is None:
            self.search.shapes = ["uptrend", "range"] if ratio else ["uptrend", "downtrend", "range"]
        if ratio and "downtrend" in self.search.shapes:
            raise ValueError("ratio mode: a falling A/B is a rising B/A, every trend is reported as an uptrend; "
                             "drop 'downtrend' from search.shapes")
        return self

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
