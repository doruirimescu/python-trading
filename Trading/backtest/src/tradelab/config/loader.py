from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import RunConfig


def load_config(path: str | Path) -> RunConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return RunConfig.model_validate(raw)


def resolved_dict(cfg: RunConfig) -> dict[str, Any]:
    return cfg.model_dump(mode="json")
