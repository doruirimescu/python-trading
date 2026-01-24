from __future__ import annotations

from typing import Annotated, Literal, Optional, Union, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


# ---------------------------
# Engine / Data (unchanged)
# ---------------------------

class EngineConfig(StrictBaseModel):
    allow_overlapping_events: bool
    freeze_mean_on_event: bool
    freeze_volatility_on_event: bool
    max_active_events: int = Field(..., ge=1)


class DataConfig(StrictBaseModel):
    price_field: str
    returns_mode: Literal["log", "simple", "none"]
    min_bars_required: int = Field(..., ge=1)
    tickers: List[str]
    period: str
    interval: str


# ---------------------------
# Mean Estimator
# ---------------------------

class RollingSMAParams(StrictBaseModel):
    window: int = Field(..., ge=1)

class MeanRollingSMAConfig(StrictBaseModel):
    type: Literal["rolling_sma"]
    params: RollingSMAParams


class EMAParams(StrictBaseModel):
    span: int = Field(..., ge=1)
    min_periods: int = Field(1, ge=1)

class MeanEMAConfig(StrictBaseModel):
    type: Literal["ema"]
    params: EMAParams


class KalmanMeanParams(StrictBaseModel):
    process_var: float = Field(..., gt=0)
    obs_var: float = Field(..., gt=0)
    init_mean: float = 0.0
    init_var: float = Field(1.0, gt=0)
    min_periods: int = Field(1, ge=1)

class MeanKalmanConfig(StrictBaseModel):
    type: Literal["kalman_mean"]
    params: KalmanMeanParams


MeanEstimatorConfig = Annotated[
    Union[MeanRollingSMAConfig, MeanEMAConfig, MeanKalmanConfig],
    Field(discriminator="type"),
]


# ---------------------------
# Volatility Estimator
# ---------------------------

class RollingStdParams(StrictBaseModel):
    window: int = Field(..., ge=1)
    min_periods: int = Field(1, ge=1)
    ddof: Literal[0, 1] = 0
    min_volatility: float = Field(0.0, ge=0)
    volatility_unit: Literal["returns", "price"] = "returns"

class VolRollingStdConfig(StrictBaseModel):
    type: Literal["rolling_std"]
    params: RollingStdParams


class EWMAVolParams(StrictBaseModel):
    span: int = Field(..., ge=1)
    min_periods: int = Field(1, ge=1)
    min_volatility: float = Field(0.0, ge=0)
    volatility_unit: Literal["returns", "price"] = "returns"

class VolEWMAConfig(StrictBaseModel):
    type: Literal["ewma"]
    params: EWMAVolParams


class GARCH11Params(StrictBaseModel):
    omega: float = Field(..., gt=0)
    alpha: float = Field(..., ge=0)
    beta: float = Field(..., ge=0)
    init_sigma2: float | None = Field(default=None, gt=0)
    min_volatility: float = Field(0.0, ge=0)
    min_periods: int = Field(1, ge=1)
    enforce_stationarity: bool = True
    volatility_unit: Literal["returns", "price"] = "returns"

    @model_validator(mode="after")
    def stationarity(self):
        if self.enforce_stationarity and (self.alpha + self.beta) >= 1.0:
            raise ValueError("Stationarity requires alpha + beta < 1")
        return self

class VolGARCH11Config(StrictBaseModel):
    type: Literal["garch11"]
    params: GARCH11Params


VolatilityEstimatorConfig = Annotated[
    Union[VolRollingStdConfig, VolEWMAConfig, VolGARCH11Config],
    Field(discriminator="type"),
]


# ---------------------------
# Deviation Detector
# ---------------------------

class ZScoreDetectorParams(StrictBaseModel):
    threshold: float = Field(..., gt=0)
    min_absolute_move: float = Field(0.0, ge=0)

class DevZScoreConfig(StrictBaseModel):
    type: Literal["zscore"]
    params: ZScoreDetectorParams

DeviationDetectorConfig = Annotated[
    Union[DevZScoreConfig],
    Field(discriminator="type"),
]


# ---------------------------
# Reversion Criteria
# ---------------------------

class SoftBandReversionParams(StrictBaseModel):
    z_tolerance: float = Field(..., gt=0)

class RevSoftBandConfig(StrictBaseModel):
    type: Literal["soft_band"]
    params: SoftBandReversionParams

ReversionCriteriaConfig = Annotated[
    Union[RevSoftBandConfig],
    Field(discriminator="type"),
]


# ---------------------------
# Failure Criteria
# ---------------------------

class CompositeFailureParams(StrictBaseModel):
    max_duration: Optional[int] = Field(default=None, gt=0)
    max_zscore: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.max_duration is None and self.max_zscore is None:
            raise ValueError("At least one failure condition must be specified")
        return self

class FailCompositeConfig(StrictBaseModel):
    type: Literal["composite"]
    params: CompositeFailureParams

FailureCriteriaConfig = Annotated[
    Union[FailCompositeConfig],
    Field(discriminator="type"),
]


# ---------------------------
# Scoring / Diagnostics (unchanged)
# ---------------------------

class ScoringConfig(StrictBaseModel):
    by_direction: bool
    by_volatility_bucket: bool
    volatility_buckets: Optional[int] = Field(default=None, ge=1)
    record_empty_scores: bool

    @model_validator(mode="after")
    def validate_buckets(self):
        if self.by_volatility_bucket and self.volatility_buckets is None:
            raise ValueError("volatility_buckets must be set when by_volatility_bucket is true")
        return self


class DiagnosticsConfig(StrictBaseModel):
    enabled: bool
    record_event_paths: bool = False
    record_max_excursion: bool = False
    record_time_to_resolution: bool = False


# ---------------------------
# Visualization
# ---------------------------

class VisualizationConfig(StrictBaseModel):
    show_ratio: bool = True
    show_log_ratio: bool = False
    show_zscore: bool = False
    show_returns: bool = False
    top_k: Optional[int] = Field(default=None, ge=1)


# ---------------------------
# Ratio Universe
# ---------------------------

class RatioUniverseConfig(StrictBaseModel):
    k_num: int = Field(..., ge=1)
    k_den: int = Field(..., ge=1)
    disallow_overlap: bool = True
    unordered_if_equal_k: bool = True
    max_jobs: Optional[int] = Field(default=None, ge=1)


# ---------------------------
# Root
# ---------------------------

class RootConfig(StrictBaseModel):
    config_version: Literal[1]

    engine: EngineConfig
    data: DataConfig

    mean_estimator: MeanEstimatorConfig
    volatility_estimator: VolatilityEstimatorConfig
    deviation_detector: DeviationDetectorConfig
    reversion_criteria: ReversionCriteriaConfig
    failure_criteria: FailureCriteriaConfig

    scoring: ScoringConfig
    diagnostics: DiagnosticsConfig
    visualization: VisualizationConfig
    ratio_universe: RatioUniverseConfig
