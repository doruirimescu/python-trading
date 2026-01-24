from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"


class EventStatus(str, Enum):
    REVERTED = "reverted"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class EventSummary:
    # identity
    direction: Direction
    status: EventStatus

    # lifecycle
    start_index: int
    end_index: int
    duration: int

    # state at entry
    start_price: float
    start_mean: float
    start_volatility: float
    start_zscore: float

    # path stats
    max_abs_zscore: float

    # timestamps (optional; engine will pass through whatever the caller provides)
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None


@dataclass(frozen=True)
class ScoreResult:
    score: float  # reverted / total_events (NaN if total_events==0 and record_empty_scores==False)
    total_events: int
    reverted_events: int
    failed_events: int
    expired_events: int

    # optional breakdowns
    by_direction: Optional[Dict[str, float]] = None
    by_volatility_bucket: Optional[Dict[str, float]] = None

    # optional raw event list (toggle in config later if you want)
    events: Optional[List[EventSummary]] = None
