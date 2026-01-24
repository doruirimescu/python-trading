from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mrscore.core.results import Direction


@dataclass(frozen=True)
class DeviationEvent:
    timestamp: object
    zscore: float
    direction: Direction
    price: Optional[float] = None
