# composition_root.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from model.config_model import RootConfig


# ============================================================
# Concrete component implementations (placeholders)
# Replace these imports/classes with your real implementations.
# ============================================================

class RollingSMA:
    def __init__(self, *, window: int) -> None:
        self.window = window

class EWMA:
    def __init__(self, *, window: int, min_volatility: float, volatility_unit: str) -> None:
        self.window = window
        self.min_volatility = min_volatility
        self.volatility_unit = volatility_unit

class ZScoreDeviationDetector:
    def __init__(self, *, threshold: float, min_absolute_move: float) -> None:
        self.threshold = threshold
        self.min_absolute_move = min_absolute_move

class SoftBandReversionCriteria:
    def __init__(self, *, z_tolerance: float) -> None:
        self.z_tolerance = z_tolerance

class CompositeFailureCriteria:
    def __init__(self, *, max_duration: int | None, max_zscore: float | None) -> None:
        self.max_duration = max_duration
        self.max_zscore = max_zscore


# ============================================================
# Application container (composition output)
# ============================================================

@dataclass(frozen=True)
class App:
    """
    The application object produced by the composition root.

    This is the single object your CLI / jobs should use.
    As you add the Engine, attach it here.
    """
    config: RootConfig

    mean_estimator: Any
    volatility_estimator: Any
    deviation_detector: Any
    reversion_criteria: Any
    failure_criteria: Any


# ============================================================
# Composition root
# ============================================================

def build_app(config: RootConfig) -> App:
    """
    Composition Root:
    - Owns all "which concrete class do we use?" decisions
    - Translates config -> concrete instances
    - Keeps the rest of the codebase free of wiring concerns
    """

    # ------------------------
    # Mean estimator
    # ------------------------
    mean_cfg = config.mean_estimator
    if mean_cfg.type == "rolling_sma":
        mean_estimator = RollingSMA(window=mean_cfg.params.window)
    else:  # pragma: no cover (discriminated union should prevent this)
        raise ValueError(f"Unsupported mean_estimator.type: {mean_cfg.type}")

    # ------------------------
    # Volatility estimator
    # ------------------------
    vol_cfg = config.volatility_estimator
    if vol_cfg.type == "ewma":
        vol_estimator = EWMA(
            window=vol_cfg.params.window,
            min_volatility=vol_cfg.params.min_volatility,
            volatility_unit=vol_cfg.params.volatility_unit,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported volatility_estimator.type: {vol_cfg.type}")

    # ------------------------
    # Deviation detector
    # ------------------------
    dev_cfg = config.deviation_detector
    if dev_cfg.type == "zscore":
        deviation_detector = ZScoreDeviationDetector(
            threshold=dev_cfg.params.threshold,
            min_absolute_move=dev_cfg.params.min_absolute_move,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported deviation_detector.type: {dev_cfg.type}")

    # ------------------------
    # Reversion criteria
    # ------------------------
    rev_cfg = config.reversion_criteria
    if rev_cfg.type == "soft_band":
        reversion_criteria = SoftBandReversionCriteria(
            z_tolerance=rev_cfg.params.z_tolerance
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported reversion_criteria.type: {rev_cfg.type}")

    # ------------------------
    # Failure criteria
    # ------------------------
    fail_cfg = config.failure_criteria
    if fail_cfg.type == "composite":
        failure_criteria = CompositeFailureCriteria(
            max_duration=fail_cfg.params.max_duration,
            max_zscore=fail_cfg.params.max_zscore,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported failure_criteria.type: {fail_cfg.type}")

    return App(
        config=config,
        mean_estimator=mean_estimator,
        volatility_estimator=vol_estimator,
        deviation_detector=deviation_detector,
        reversion_criteria=reversion_criteria,
        failure_criteria=failure_criteria,
    )
