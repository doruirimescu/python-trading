# config_loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generic, Mapping, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from model.model import (
    RootConfig,
    MeanEstimatorConfig,
    VolatilityEstimatorConfig,
    DeviationDetectorConfig,
    ReversionCriteriaConfig,
    FailureCriteriaConfig,
)

# ============================================================
# Errors
# ============================================================

class ConfigError(Exception):
    """Base class for configuration-related failures."""


class ConfigLoadError(ConfigError):
    """Raised when YAML cannot be loaded or is malformed."""


class ConfigValidationError(ConfigError):
    """Raised when RootConfig schema validation fails."""


class RegistryResolutionError(ConfigError):
    """Raised when a plugin type or plugin params cannot be resolved/validated."""


# ============================================================
# YAML Load
# ============================================================

def load_yaml_file(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ConfigLoadError(f"Config file not found: {p}")

    try:
        import yaml  # PyYAML
    except Exception as e:
        raise ConfigLoadError(
            "PyYAML is required to load YAML configs. Install it with: pip install pyyaml"
        ) from e

    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigLoadError(f"Failed to parse YAML: {p}") from e

    if data is None:
        raise ConfigLoadError(f"Config file is empty: {p}")
    if not isinstance(data, dict):
        raise ConfigLoadError(f"Top-level YAML must be a mapping/object: {p}")

    return data


# ============================================================
# Plugin Param Schemas (strict)
# ============================================================

class StrictParamsModel(BaseModel):
    class Config:
        extra = "forbid"
        allow_mutation = False


# NOTE:
# These are example param models for built-in plugins.
# Add/extend as you implement plugins. The registry validates against these.

class RollingSMAParams(StrictParamsModel):
    window: int

class EWMAParams(StrictParamsModel):
    window: int
    min_volatility: float
    volatility_unit: str  # validated in RootConfig as returns|price; registry can be stricter if desired

class ZScoreDetectorParams(StrictParamsModel):
    threshold: float
    min_absolute_move: float = 0.0

class SoftBandReversionParams(StrictParamsModel):
    z_tolerance: float

class CompositeFailureParams(StrictParamsModel):
    max_duration: Optional[int] = None
    max_zscore: Optional[float] = None


# ============================================================
# Registry Types
# ============================================================

TPlugin = TypeVar("TPlugin")
TParams = TypeVar("TParams", bound=StrictParamsModel)

@dataclass(frozen=True)
class PluginSpec(Generic[TPlugin, TParams]):
    plugin_cls: Type[TPlugin]
    params_model: Type[TParams]


class Registry(Generic[TPlugin]):
    """
    String-keyed registry that validates existence and plugin-specific params via Pydantic models.
    """
    def __init__(self, name: str):
        self._name = name
        self._specs: Dict[str, PluginSpec[TPlugin, StrictParamsModel]] = {}

    def register(self, type_name: str, plugin_cls: Type[TPlugin], params_model: Type[StrictParamsModel]) -> None:
        if not type_name or not isinstance(type_name, str):
            raise ValueError("type_name must be a non-empty string")
        if type_name in self._specs:
            raise ValueError(f"Duplicate registration in {self._name}: '{type_name}'")
        self._specs[type_name] = PluginSpec(plugin_cls=plugin_cls, params_model=params_model)

    def resolve(self, type_name: str) -> PluginSpec[TPlugin, StrictParamsModel]:
        try:
            return self._specs[type_name]
        except KeyError as e:
            available = ", ".join(sorted(self._specs.keys())) or "(none registered)"
            raise RegistryResolutionError(
                f"Unknown {self._name} plugin type '{type_name}'. Available: {available}"
            ) from e

    def validate_params(self, type_name: str, params: Mapping[str, Any]) -> StrictParamsModel:
        spec = self.resolve(type_name)
        try:
            return spec.params_model.parse_obj(dict(params))
        except ValidationError as e:
            # Provide contextual error message that points directly at the component and type.
            raise RegistryResolutionError(
                f"Invalid params for {self._name} '{type_name}': {e}"
            ) from e


# ============================================================
# Concrete Registries
# ============================================================

MeanEstimatorRegistry = Registry[Any]("mean_estimator")
VolatilityEstimatorRegistry = Registry[Any]("volatility_estimator")
DeviationDetectorRegistry = Registry[Any]("deviation_detector")
ReversionCriteriaRegistry = Registry[Any]("reversion_criteria")
FailureCriteriaRegistry = Registry[Any]("failure_criteria")


# ============================================================
# Runtime Resolved Config (immutable)
# ============================================================

@dataclass(frozen=True)
class ResolvedComponent(Generic[TPlugin]):
    type_name: str
    plugin_cls: Type[TPlugin]
    params: StrictParamsModel


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Fully validated + registry-resolved configuration.
    This is what the Engine should receive (never raw YAML).
    """
    raw: RootConfig

    mean_estimator: ResolvedComponent[Any]
    volatility_estimator: ResolvedComponent[Any]
    deviation_detector: ResolvedComponent[Any]
    reversion_criteria: ResolvedComponent[Any]
    failure_criteria: ResolvedComponent[Any]


# ============================================================
# Registry Bootstrap (example)
# ============================================================

def register_builtin_plugins() -> None:
    """
    Register built-in plugin types.

    Replace placeholder plugin classes with your concrete implementations as they are created.
    This function is intentionally explicit (no reflection/magic).
    """

    # --- Placeholder classes (swap with real implementations) ---
    class RollingSMA: ...
    class EWMA: ...
    class ZScoreDetector: ...
    class SoftBandReversion: ...
    class CompositeFailure: ...

    # Mean
    MeanEstimatorRegistry.register("rolling_sma", RollingSMA, RollingSMAParams)

    # Volatility
    VolatilityEstimatorRegistry.register("ewma", EWMA, EWMAParams)

    # Deviation
    DeviationDetectorRegistry.register("zscore", ZScoreDetector, ZScoreDetectorParams)

    # Reversion
    ReversionCriteriaRegistry.register("soft_band", SoftBandReversion, SoftBandReversionParams)

    # Failure
    FailureCriteriaRegistry.register("composite", CompositeFailure, CompositeFailureParams)


# ============================================================
# Parsing + Resolution
# ============================================================

def parse_root_config(config_dict: Mapping[str, Any]) -> RootConfig:
    try:
        return RootConfig.parse_obj(dict(config_dict))
    except ValidationError as e:
        raise ConfigValidationError(f"Config schema validation failed: {e}") from e


def _resolve_component(
    section_name: str,
    component_cfg: Any,  # MeanEstimatorConfig, etc.
    registry: Registry[Any],
) -> ResolvedComponent[Any]:
    if not hasattr(component_cfg, "type") or not hasattr(component_cfg, "params"):
        raise RegistryResolutionError(f"Invalid component config for '{section_name}'")

    type_name = component_cfg.type
    params = component_cfg.params

    # Ensure params is a mapping (RootConfig already enforces Dict[str, object], but keep defensive checks)
    if not isinstance(params, dict):
        raise RegistryResolutionError(f"'{section_name}.params' must be a mapping/object")

    spec = registry.resolve(type_name)
    validated_params = registry.validate_params(type_name, params)

    return ResolvedComponent(
        type_name=type_name,
        plugin_cls=spec.plugin_cls,
        params=validated_params,
    )


def resolve_registries(root: RootConfig) -> RuntimeConfig:
    """
    Convert schema-validated RootConfig into a fully resolved RuntimeConfig:
    - plugin type names validated against registries
    - plugin params validated against plugin param models (extra keys forbidden)
    """
    mean_res = _resolve_component("mean_estimator", root.mean_estimator, MeanEstimatorRegistry)
    vol_res = _resolve_component("volatility_estimator", root.volatility_estimator, VolatilityEstimatorRegistry)
    dev_res = _resolve_component("deviation_detector", root.deviation_detector, DeviationDetectorRegistry)
    rev_res = _resolve_component("reversion_criteria", root.reversion_criteria, ReversionCriteriaRegistry)
    fail_res = _resolve_component("failure_criteria", root.failure_criteria, FailureCriteriaRegistry)

    return RuntimeConfig(
        raw=root,
        mean_estimator=mean_res,
        volatility_estimator=vol_res,
        deviation_detector=dev_res,
        reversion_criteria=rev_res,
        failure_criteria=fail_res,
    )


def load_config(path: str | Path, *, register_builtins: bool = True) -> RuntimeConfig:
    """
    Primary entrypoint:
      YAML file -> RootConfig (Pydantic) -> Registry resolution -> RuntimeConfig

    This function fails fast and never returns a partially-valid config.
    """
    if register_builtins:
        # Idempotency: callers may invoke multiple times in a single process.
        # If you prefer strict single-init, move registration to app startup and remove this.
        _safe_register_builtins_once()

    config_dict = load_yaml_file(path)
    root = parse_root_config(config_dict)
    return resolve_registries(root)


# ============================================================
# Internal: safe one-time registration
# ============================================================

_BUILTINS_REGISTERED = False

def _safe_register_builtins_once() -> None:
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return
    register_builtin_plugins()
    _BUILTINS_REGISTERED = True
