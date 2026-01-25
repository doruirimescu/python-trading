import numpy as np

from mrscore.config.models import DiagnosticsConfig, ScoringConfig
from mrscore.core.results import Direction, EventStatus, EventSummary
from mrscore.core.scoring import score_events


def _event(direction: Direction, status: EventStatus, vol: float) -> EventSummary:
    return EventSummary(
        direction=direction,
        status=status,
        start_index=0,
        end_index=0,
        duration=0,
        start_price=0.0,
        start_mean=0.0,
        start_volatility=float(vol),
        start_zscore=0.0,
        max_abs_zscore=0.0,
    )


def test_score_events_basic_breakdowns():
    scoring = ScoringConfig(
        by_direction=True,
        by_volatility_bucket=True,
        volatility_buckets=2,
        record_empty_scores=False,
    )
    diagnostics = DiagnosticsConfig(enabled=True)

    events = [
        _event(Direction.UP, EventStatus.REVERTED, 1.0),
        _event(Direction.UP, EventStatus.FAILED, 2.0),
        _event(Direction.DOWN, EventStatus.REVERTED, 3.0),
        _event(Direction.DOWN, EventStatus.FAILED, 4.0),
    ]

    result = score_events(events=events, scoring=scoring, diagnostics=diagnostics)

    assert result.total_events == 4
    assert result.reverted_events == 2
    assert result.failed_events == 2
    assert result.expired_events == 0
    assert result.score == 0.5
    assert result.by_direction == {Direction.UP.value: 0.5, Direction.DOWN.value: 0.5}
    assert result.by_volatility_bucket == {"bucket_0": 0.5, "bucket_1": 0.5}
    assert result.events is not None
    assert len(result.events) == 4
    assert result.events[0].status == EventStatus.REVERTED


def test_score_events_empty_events_nan_when_not_recording():
    scoring = ScoringConfig(
        by_direction=True,
        by_volatility_bucket=True,
        volatility_buckets=3,
        record_empty_scores=False,
    )
    diagnostics = DiagnosticsConfig(enabled=False)

    result = score_events(events=[], scoring=scoring, diagnostics=diagnostics)

    assert result.total_events == 0
    assert np.isnan(result.score)
    assert result.events is None
    assert result.by_direction is not None
    assert np.isnan(result.by_direction[Direction.UP.value])
    assert np.isnan(result.by_direction[Direction.DOWN.value])
    assert result.by_volatility_bucket is not None
    assert np.isnan(result.by_volatility_bucket["bucket_0"])
