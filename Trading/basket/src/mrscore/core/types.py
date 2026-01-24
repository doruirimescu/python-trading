from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class DeviationEvent:
    timestamp: object
    zscore: float
    direction: Direction
    price: Optional[float] = None
