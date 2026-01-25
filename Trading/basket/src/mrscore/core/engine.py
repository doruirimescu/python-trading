from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Any, List, Optional

import numpy as np

from mrscore.config.models import RootConfig
from mrscore.core.results import Direction, EventStatus, EventSummary, ScoreResult
from mrscore.core.scoring import score_events


@dataclass
class _ActiveEvent:
    direction: Direction
    start_index: int
    start_time: Optional[Any]

    start_price: float
    start_mean: float
    start_volatility: float
    start_zscore: float

    max_abs_zscore: float


class MeanReversionEngine:
    """
    Streams a single time series (prices + optional returns) and scores how often
    deviations revert to the mean.

    Event lifecycle:
      - open: detector signals deviation beyond threshold
      - revert: reversion_criteria says z back inside tolerance
      - fail: failure_criteria triggers (duration, max_zscore, etc.)
      - expire: series ended while still active
    """

    def __init__(
        self,
        *,
        config: RootConfig,
        mean_estimator: Any,
        volatility_estimator: Any,
        deviation_detector: Any,
        reversion_criteria: Any,
        failure_criteria: Any,
        volatility_unit: str,
    ) -> None:
        self.config = config

        self.mean_estimator = mean_estimator
        self.volatility_estimator = volatility_estimator
        self.deviation_detector = deviation_detector
        self.reversion_criteria = reversion_criteria
        self.failure_criteria = failure_criteria

        if volatility_unit not in ("returns", "price"):
            raise ValueError("volatility_unit must be 'returns' or 'price'")
        self.volatility_unit = volatility_unit

    def run(
        self,
        *,
        prices: np.ndarray,
        returns: Optional[np.ndarray],
        dates: Optional[np.ndarray] = None,
    ) -> ScoreResult:
        prices = np.asarray(prices, dtype=np.float64)
        if prices.ndim != 1:
            raise ValueError("prices must be 1D")
        T = int(prices.shape[0])
        if T == 0:
            return ScoreResult(
                score=float("nan"),
                total_events=0,
                reverted_events=0,
                failed_events=0,
                expired_events=0,
                by_direction=None,
                by_volatility_bucket=None,
                events=[],
            )

        if dates is not None:
            if len(dates) != T:
                raise ValueError("dates length must match prices length")
        # returns are only needed if volatility_unit == "returns"
        if self.volatility_unit == "returns":
            if returns is None:
                raise ValueError("returns must be provided when volatility_unit='returns'")
            returns = np.asarray(returns, dtype=np.float64)
            if returns.ndim != 1 or len(returns) != T - 1:
                raise ValueError("returns must be 1D of length T-1")

        # reset components per series (important for batch scanning)
        self.mean_estimator.reset()
        self.volatility_estimator.reset()

        eng_cfg = self.config.engine
        data_cfg = self.config.data
        scoring_cfg = self.config.scoring

        allow_overlapping = bool(eng_cfg.allow_overlapping_events)
        freeze_mean_on_event = bool(eng_cfg.freeze_mean_on_event)
        freeze_vol_on_event = bool(eng_cfg.freeze_volatility_on_event)
        max_active_events = int(eng_cfg.max_active_events)

        min_bars_required = int(data_cfg.min_bars_required)

        active: List[_ActiveEvent] = []
        summaries: List[EventSummary] = []

        # main loop
        for t in range(T):
            p = float(prices[t])
            now = dates[t] if dates is not None else None

            # update mean unless frozen by active event(s)
            if not (freeze_mean_on_event and active):
                self.mean_estimator.update(p)

            # update volatility (price or returns) unless frozen by active event(s)
            if self.volatility_unit == "price":
                if not (freeze_vol_on_event and active):
                    self.volatility_estimator.update(p)
            else:
                # returns-based vol: update from t=1 onward
                if t >= 1 and not (freeze_vol_on_event and active):
                    self.volatility_estimator.update(float(returns[t - 1]))

            # enforce warmup / readiness
            if t + 1 < min_bars_required:
                continue
            if not self.mean_estimator.is_ready():
                continue
            if not self.volatility_estimator.is_ready():
                continue

            mean = float(self.mean_estimator.value)
            vol = float(self.volatility_estimator.value)
            if not np.isfinite(mean) or not np.isfinite(vol) or vol <= 0.0:
                continue

            z = (p - mean) / vol
            if not np.isfinite(z):
                continue

            # 1) update active events (revert / fail)
            if active:
                still_active: List[_ActiveEvent] = []
                for ev in active:
                    dur = t - ev.start_index
                    max_abs = ev.max_abs_zscore
                    az = abs(z)
                    if az > max_abs:
                        max_abs = az

                    # reversion beats failure if both happen same bar
                    if self.reversion_criteria.is_reverted(zscore=z):
                        summaries.append(
                            EventSummary(
                                direction=ev.direction,
                                status=EventStatus.REVERTED,
                                start_index=ev.start_index,
                                end_index=t,
                                duration=dur,
                                start_price=ev.start_price,
                                start_mean=ev.start_mean,
                                start_volatility=ev.start_volatility,
                                start_zscore=ev.start_zscore,
                                max_abs_zscore=max_abs,
                                start_time=ev.start_time,
                                end_time=now,
                            )
                        )
                        continue

                    if self.failure_criteria.is_failed(duration=dur, zscore=z):
                        summaries.append(
                            EventSummary(
                                direction=ev.direction,
                                status=EventStatus.FAILED,
                                start_index=ev.start_index,
                                end_index=t,
                                duration=dur,
                                start_price=ev.start_price,
                                start_mean=ev.start_mean,
                                start_volatility=ev.start_volatility,
                                start_zscore=ev.start_zscore,
                                max_abs_zscore=max_abs,
                                start_time=ev.start_time,
                                end_time=now,
                            )
                        )
                        continue

                    ev.max_abs_zscore = max_abs
                    still_active.append(ev)

                active = still_active

            # 2) open new event(s) if allowed
            can_open = (len(active) < max_active_events) and (allow_overlapping or not active)
            if can_open:
                direction = self.deviation_detector.detect(price=p, mean=mean, volatility=vol)
                if direction is not None:
                    active.append(
                        _ActiveEvent(
                            direction=direction,
                            start_index=t,
                            start_time=now,
                            start_price=p,
                            start_mean=mean,
                            start_volatility=vol,
                            start_zscore=z,
                            max_abs_zscore=abs(z),
                        )
                    )

        # expire remaining actives
        if active:
            t_end = T - 1
            end_time = dates[t_end] if dates is not None else None
            for ev in active:
                dur = t_end - ev.start_index
                summaries.append(
                    EventSummary(
                        direction=ev.direction,
                        status=EventStatus.EXPIRED,
                        start_index=ev.start_index,
                        end_index=t_end,
                        duration=dur,
                        start_price=ev.start_price,
                        start_mean=ev.start_mean,
                        start_volatility=ev.start_volatility,
                        start_zscore=ev.start_zscore,
                        max_abs_zscore=ev.max_abs_zscore,
                        start_time=ev.start_time,
                        end_time=end_time,
                    )
                )

        return score_events(
            events=summaries,
            scoring=scoring_cfg,
            diagnostics=self.config.diagnostics,
        )
