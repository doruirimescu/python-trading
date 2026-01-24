from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import ValidationError

from model.config_model import RootConfig


class ConfigError(Exception):
    """Base class for configuration-related failures."""


class ConfigLoadError(ConfigError):
    """Raised when YAML cannot be loaded or is malformed."""


class ConfigValidationError(ConfigError):
    """Raised when RootConfig schema validation fails."""


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Fully schema-validated configuration.

    v1 intentionally stops at schema validation (no registry/resolution).
    """
    raw: RootConfig


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


def parse_root_config(config_dict: Mapping[str, Any]) -> RootConfig:
    try:
        return RootConfig.model_validate(dict(config_dict))
    except ValidationError as e:
        raise ConfigValidationError(f"Config schema validation failed: {e}") from e


def load_config(path: str | Path) -> RuntimeConfig:
    config_dict = load_yaml_file(path)
    root = parse_root_config(config_dict)
    return RuntimeConfig(raw=root)
