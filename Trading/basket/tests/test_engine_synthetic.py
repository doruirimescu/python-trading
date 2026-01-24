import numpy as np
import pytest

from mrscore.components.deviation.zscore import ZScoreDeviationDetector
from mrscore.components.failure.composite import CompositeFailureCriteria
from mrscore.components.reversion.soft_band import SoftBandReversionCriteria
from mrscore.config.models import RootConfig
from mrscore.core.engine import MeanReversionEngine
from mrscore.core.results import Direction, EventStatus


class ConstantEstimator:
    def __init__(self, value: float) -> None:
        self.value = float(value)
        self.update_calls = 0

    def reset(self) -> None:
        self.update_calls = 0

    def is_ready(self) -> bool:
        return True

    def update(self, _: float) -> float:
        self.update_calls += 1
        return self.value


class OneShotDetector:
    def __init__(self, direction: Direction) -> None:
        self._direction = direction
        self._used = False

    def detect(self, *, price: float, mean: float, volatility: float) -> Direction | None:
        if self._used:
            return None
        self._used = True
        return self._direction


class NeverRevert:
    def is_reverted(self, *, zscore: float) -> bool:
        return False


class NeverFail:
    def is_failed(self, *, duration: int, zscore: float) -> bool:
        return False


def build_config(
    *,
    allow_overlapping_events: bool = False,
    freeze_mean_on_event: bool = False,
    freeze_volatility_on_event: bool = False,
    max_active_events: int = 1,
    min_bars_required: int = 1,
    volatility_unit: str = "price",
    record_empty_scores: bool = True,
    diagnostics_enabled: bool = True,
    by_direction: bool = True,
    failure_max_duration: int | None = 5,
    failure_max_zscore: float | None = 3.0,
) -> RootConfig:
    return RootConfig.model_validate(
        {
            "config_version": 1,
            "engine": {
                "allow_overlapping_events": allow_overlapping_events,
                "freeze_mean_on_event": freeze_mean_on_event,
                "freeze_volatility_on_event": freeze_volatility_on_event,
                "max_active_events": max_active_events,
            },
            "data": {
                "price_field": "close",
                "returns_mode": "none",
                "min_bars_required": min_bars_required,
                "tickers": ["TEST"],
                "period": "1d",
                "interval": "1d",
            },
            "mean_estimator": {"type": "rolling_sma", "params": {"window": 1}},
            "volatility_estimator": {
                "type": "rolling_std",
                "params": {
                    "window": 1,
                    "min_periods": 1,
                    "ddof": 0,
                    "min_volatility": 0.0,
                    "volatility_unit": volatility_unit,
                },
            },
            "deviation_detector": {"type": "zscore", "params": {"threshold": 1.0, "min_absolute_move": 0.0}},
            "reversion_criteria": {"type": "soft_band", "params": {"z_tolerance": 0.5}},
            "failure_criteria": {
                "type": "composite",
                "params": {"max_duration": failure_max_duration, "max_zscore": failure_max_zscore},
            },
            "scoring": {
                "by_direction": by_direction,
                "by_volatility_bucket": False,
                "volatility_buckets": None,
                "record_empty_scores": record_empty_scores,
            },
            "diagnostics": {
                "enabled": diagnostics_enabled,
                "record_event_paths": False,
                "record_max_excursion": False,
                "record_time_to_resolution": False,
            },
            "visualization": {
                "show_ratio": True,
                "show_log_ratio": False,
                "show_zscore": False,
                "show_returns": False,
                "top_k": None,
            },
            "ratio_universe": {
                "k_num": 1,
                "k_den": 1,
                "disallow_overlap": True,
                "unordered_if_equal_k": True,
                "max_jobs": None,
            },
        }
    )


def test_engine_reverted_event_scores():
    config = build_config()
    engine = MeanReversionEngine(
        config=config,
        mean_estimator=ConstantEstimator(0.0),
        volatility_estimator=ConstantEstimator(1.0),
        deviation_detector=ZScoreDeviationDetector(threshold=1.0, min_absolute_move=0.0),
        reversion_criteria=SoftBandReversionCriteria(z_tolerance=0.5),
        failure_criteria=CompositeFailureCriteria(max_duration=10, max_zscore=5.0),
        volatility_unit="price",
    )

    prices = np.array([0.0, 2.0, 0.2, 0.1], dtype=np.float64)
    result = engine.run(prices=prices, returns=None)

    assert result.total_events == 1
    assert result.reverted_events == 1
    assert result.failed_events == 0
    assert result.expired_events == 0
    assert result.score == 1.0
    assert result.by_direction == {Direction.UP.value: 0.0, Direction.DOWN.value: 1.0}

    assert result.events is not None
    event = result.events[0]
    assert event.status == EventStatus.REVERTED
    assert event.direction == Direction.DOWN
    assert event.start_index == 1
    assert event.end_index == 2


def test_engine_failed_by_duration():
    config = build_config(failure_max_duration=1, failure_max_zscore=None)
    engine = MeanReversionEngine(
        config=config,
        mean_estimator=ConstantEstimator(0.0),
        volatility_estimator=ConstantEstimator(1.0),
        deviation_detector=OneShotDetector(Direction.DOWN),
        reversion_criteria=NeverRevert(),
        failure_criteria=CompositeFailureCriteria(max_duration=1, max_zscore=None),
        volatility_unit="price",
    )

    prices = np.array([0.0, 2.0], dtype=np.float64)
    result = engine.run(prices=prices, returns=None)

    assert result.total_events == 1
    assert result.reverted_events == 0
    assert result.failed_events == 1
    assert result.expired_events == 0
    assert result.score == 0.0
    assert result.events is not None
    assert result.events[0].status == EventStatus.FAILED
    assert result.events[0].end_index == 1


def test_engine_expired_event():
    config = build_config(failure_max_duration=100, failure_max_zscore=100.0)
    engine = MeanReversionEngine(
        config=config,
        mean_estimator=ConstantEstimator(0.0),
        volatility_estimator=ConstantEstimator(1.0),
        deviation_detector=ZScoreDeviationDetector(threshold=1.0, min_absolute_move=0.0),
        reversion_criteria=SoftBandReversionCriteria(z_tolerance=0.1),
        failure_criteria=CompositeFailureCriteria(max_duration=100, max_zscore=100.0),
        volatility_unit="price",
    )

    prices = np.array([0.0, 2.0, 2.0], dtype=np.float64)
    result = engine.run(prices=prices, returns=None)

    assert result.total_events == 1
    assert result.reverted_events == 0
    assert result.failed_events == 0
    assert result.expired_events == 1
    assert result.events is not None
    assert result.events[0].status == EventStatus.EXPIRED


def test_engine_requires_returns_when_configured():
    config = build_config(volatility_unit="returns")
    engine = MeanReversionEngine(
        config=config,
        mean_estimator=ConstantEstimator(0.0),
        volatility_estimator=ConstantEstimator(1.0),
        deviation_detector=ZScoreDeviationDetector(threshold=1.0, min_absolute_move=0.0),
        reversion_criteria=SoftBandReversionCriteria(z_tolerance=0.5),
        failure_criteria=CompositeFailureCriteria(max_duration=10, max_zscore=5.0),
        volatility_unit="returns",
    )

    prices = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    with pytest.raises(ValueError, match="returns must be provided"):
        engine.run(prices=prices, returns=None)


def test_freeze_updates_on_active_event():
    config = build_config(freeze_mean_on_event=True, freeze_volatility_on_event=True)
    mean_estimator = ConstantEstimator(0.0)
    vol_estimator = ConstantEstimator(1.0)
    engine = MeanReversionEngine(
        config=config,
        mean_estimator=mean_estimator,
        volatility_estimator=vol_estimator,
        deviation_detector=OneShotDetector(Direction.DOWN),
        reversion_criteria=NeverRevert(),
        failure_criteria=NeverFail(),
        volatility_unit="price",
    )

    prices = np.array([0.0, 0.1, 0.2, 0.3], dtype=np.float64)
    result = engine.run(prices=prices, returns=None)

    assert mean_estimator.update_calls == 1
    assert vol_estimator.update_calls == 1
    assert result.expired_events == 1
