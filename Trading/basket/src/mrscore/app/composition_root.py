from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mrscore.components.deviation.zscore import ZScoreDeviationDetector
from mrscore.components.failure.composite import CompositeFailureCriteria
from mrscore.components.mean import RollingSMA, EMA, KalmanMean
from mrscore.components.reversion.soft_band import SoftBandReversionCriteria
from mrscore.components.volatility import EWMAVol, GARCH11Vol, RollingStd
from mrscore.config.models import RootConfig
from mrscore.core.engine import MeanReversionEngine

# NEW
from mrscore.backtest.backtester import RatioMeanReversionBacktester


@dataclass(frozen=True)
class App:
    config: RootConfig

    mean_estimator: Any
    volatility_estimator: Any
    deviation_detector: Any
    reversion_criteria: Any
    failure_criteria: Any

    engine: MeanReversionEngine

    # NEW (optional so you can keep backtesting disabled)
    backtester: Optional[RatioMeanReversionBacktester] = None


def build_app(config: RootConfig) -> App:
    # --- mean estimator ---
    mean_cfg = config.mean_estimator
    if mean_cfg.type == "rolling_sma":
        mean_estimator = RollingSMA(window=mean_cfg.params.window)
    elif mean_cfg.type == "ema":
        mean_estimator = EMA(span=mean_cfg.params.span, min_periods=mean_cfg.params.min_periods)
    elif mean_cfg.type == "kalman_mean":
        p = mean_cfg.params
        mean_estimator = KalmanMean(
            process_var=p.process_var,
            obs_var=p.obs_var,
            init_mean=p.init_mean,
            init_var=p.init_var,
            min_periods=p.min_periods,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported mean_estimator.type: {mean_cfg.type}")

    # --- volatility estimator ---
    vol_cfg = config.volatility_estimator
    if vol_cfg.type == "rolling_std":
        p = vol_cfg.params
        vol_estimator = RollingStd(
            window=p.window,
            min_periods=p.min_periods,
            ddof=p.ddof,
            min_volatility=p.min_volatility,
        )
        volatility_unit = p.volatility_unit
    elif vol_cfg.type == "ewma":
        p = vol_cfg.params
        vol_estimator = EWMAVol(
            span=p.span,
            min_periods=p.min_periods,
            min_volatility=p.min_volatility,
        )
        volatility_unit = p.volatility_unit
    elif vol_cfg.type == "garch11":
        p = vol_cfg.params
        vol_estimator = GARCH11Vol(
            omega=p.omega,
            alpha=p.alpha,
            beta=p.beta,
            init_sigma2=p.init_sigma2,
            min_volatility=p.min_volatility,
            min_periods=p.min_periods,
            enforce_stationarity=p.enforce_stationarity,
        )
        volatility_unit = p.volatility_unit
    else:  # pragma: no cover
        raise ValueError(f"Unsupported volatility_estimator.type: {vol_cfg.type}")

    # --- deviation detector ---
    dev_cfg = config.deviation_detector
    if dev_cfg.type == "zscore":
        deviation_detector = ZScoreDeviationDetector(
            threshold=dev_cfg.params.threshold,
            min_absolute_move=dev_cfg.params.min_absolute_move,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported deviation_detector.type: {dev_cfg.type}")

    # --- reversion criteria ---
    rev_cfg = config.reversion_criteria
    if rev_cfg.type == "soft_band":
        reversion_criteria = SoftBandReversionCriteria(z_tolerance=rev_cfg.params.z_tolerance)
    else:  # pragma: no cover
        raise ValueError(f"Unsupported reversion_criteria.type: {rev_cfg.type}")

    # --- failure criteria ---
    fail_cfg = config.failure_criteria
    if fail_cfg.type == "composite":
        failure_criteria = CompositeFailureCriteria(
            max_duration=fail_cfg.params.max_duration,
            max_zscore=fail_cfg.params.max_zscore,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported failure_criteria.type: {fail_cfg.type}")

    engine = MeanReversionEngine(
        config=config,
        mean_estimator=mean_estimator,
        volatility_estimator=vol_estimator,
        deviation_detector=deviation_detector,
        reversion_criteria=reversion_criteria,
        failure_criteria=failure_criteria,
        volatility_unit=volatility_unit,
    )

    # NEW: backtester wiring
    backtester: Optional[RatioMeanReversionBacktester] = None
    if config.backtest is not None and config.backtest.enabled:
        backtester = RatioMeanReversionBacktester(
            config=config,
            mean_estimator=mean_estimator,
            volatility_estimator=vol_estimator,
            deviation_detector=deviation_detector,
            reversion_criteria=reversion_criteria,
            failure_criteria=failure_criteria,
        )

    return App(
        config=config,
        mean_estimator=mean_estimator,
        volatility_estimator=vol_estimator,
        deviation_detector=deviation_detector,
        reversion_criteria=reversion_criteria,
        failure_criteria=failure_criteria,
        engine=engine,
        backtester=backtester,
    )
