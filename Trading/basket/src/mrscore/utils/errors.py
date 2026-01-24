from __future__ import annotations


class ConfigError(Exception):
    """Base class for configuration-related failures."""


class ConfigLoadError(ConfigError):
    """Raised when YAML cannot be loaded or is malformed."""


class ConfigValidationError(ConfigError):
    """Raised when RootConfig schema validation fails."""
