# config_models.py
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field, root_validator, validator


# ============================================================
# Base Model (Strict)
# ============================================================

class StrictBaseModel(BaseModel):
    class Config:
        extra = "forbid"
        allow_mutation = False
        validate_assignment = True


# ============================================================
# Engine
# ============================================================

class EngineConfig(StrictBaseModel):
    allow_overlapping_events: bool
    freeze_mean_on_event: bool
    freeze_volatility_on_event: bool
    max_active_events: int = Field(..., ge=1)


# ============================================================
# Data
# ============================================================

class DataConfig(StrictBaseModel):
    price_field: str
    returns_mode: Literal["log", "simple", "none"]
    min_bars_required: int = Field(..., ge=1)


# ============================================================
# Pluggable Component Base
# ============================================================

class PluggableComponentConfig(StrictBaseModel):
    type: str
    params: Dict[str, object]


# ============================================================
# Mean Estimator
# ============================================================

class MeanEstimatorConfig(PluggableComponentConfig):
    pass


# ============================================================
# Volatility Estimator
# ============================================================

class VolatilityEstimatorConfig(PluggableComponentConfig):
    @validator("params")
    def validate_volatility_unit(cls, params: Dict[str, object]):
        unit = params.get("volatility_unit")
        if unit is not None and unit not in {"returns", "price"}:
            raise ValueError(
                "volatility_unit must be one of {'returns', 'price'}"
            )
        return params


# ============================================================
# Deviation Detector
# ============================================================

class DeviationDetectorConfig(PluggableComponentConfig):
    @validator("params")
    def validate_threshold(cls, params: Dict[str, object]):
        threshold = params.get("threshold")
        if threshold is None or threshold <= 0:
            raise ValueError("threshold must be a positive float")
        return params


# ============================================================
# Reversion Criteria
# ============================================================

class ReversionCriteriaConfig(PluggableComponentConfig):
    @validator("params")
    def validate_tolerance(cls, params: Dict[str, object]):
        tol = params.get("z_tolerance")
        if tol is None or tol <= 0:
            raise ValueError("z_tolerance must be a positive float")
        return params


# ============================================================
# Failure Criteria
# ============================================================

class FailureCriteriaConfig(PluggableComponentConfig):
    @validator("params")
    def validate_failure_params(cls, params: Dict[str, object]):
        max_duration = params.get("max_duration")
        max_z = params.get("max_zscore")

        if max_duration is not None and max_duration <= 0:
            raise ValueError("max_duration must be > 0")

        if max_z is not None and max_z <= 0:
            raise ValueError("max_zscore must be > 0")

        if max_duration is None and max_z is None:
            raise ValueError(
                "At least one failure condition must be specified"
            )

        return params


# ============================================================
# Scoring
# ============================================================

class ScoringConfig(StrictBaseModel):
    by_direction: bool
    by_volatility_bucket: bool
    volatility_buckets: Optional[int] = Field(default=None, ge=1)
    record_empty_scores: bool

    @root_validator
    def validate_buckets(cls, values):
        if values.get("by_volatility_bucket") and values.get("volatility_buckets") is None:
            raise ValueError(
                "volatility_buckets must be set when by_volatility_bucket is true"
            )
        return values


# ============================================================
# Diagnostics
# ============================================================

class DiagnosticsConfig(StrictBaseModel):
    enabled: bool
    record_event_paths: Optional[bool] = False
    record_max_excursion: Optional[bool] = False
    record_time_to_resolution: Optional[bool] = False


# ============================================================
# Root Config
# ============================================================

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
