from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Any, Dict, List, Optional

import numpy as np

from mrscore.config.models import RootConfig
from mrscore.core.results import Direction, EventStatus, EventSummary, ScoreResult


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

        # score aggregation
        total = len(summaries)
        reverted = sum(1 for e in summaries if e.status == EventStatus.REVERTED)
        failed = sum(1 for e in summaries if e.status == EventStatus.FAILED)
        expired = sum(1 for e in summaries if e.status == EventStatus.EXPIRED)

        if total == 0 and not scoring_cfg.record_empty_scores:
            score = float("nan")
        else:
            score = (reverted / total) if total > 0 else 0.0

        by_dir: Optional[Dict[str, float]] = None
        if scoring_cfg.by_direction:
            up_total = sum(1 for e in summaries if e.direction == Direction.UP)
            dn_total = total - up_total
            up_rev = sum(1 for e in summaries if e.direction == Direction.UP and e.status == EventStatus.REVERTED)
            dn_rev = sum(1 for e in summaries if e.direction == Direction.DOWN and e.status == EventStatus.REVERTED)

            def _ratio(a: int, b: int) -> float:
                if b == 0:
                    return float("nan") if not scoring_cfg.record_empty_scores else 0.0
                return a / b

            by_dir = {
                Direction.UP.value: _ratio(up_rev, up_total),
                Direction.DOWN.value: _ratio(dn_rev, dn_total),
            }

        by_vol: Optional[Dict[str, float]] = None
        if scoring_cfg.by_volatility_bucket:
            k = int(scoring_cfg.volatility_buckets or 0)
            if k <= 0:
                raise ValueError("volatility_buckets must be set when by_volatility_bucket is true")

            vols = np.array([e.start_volatility for e in summaries], dtype=np.float64)
            vols = vols[np.isfinite(vols)]
            if vols.size == 0:
                by_vol = {f"bucket_{i}": (0.0 if scoring_cfg.record_empty_scores else float("nan")) for i in range(k)}
            else:
                # k buckets => k-1 quantile cut points
                qs = np.linspace(0.0, 1.0, num=k + 1)[1:-1]
                cuts = np.quantile(vols, qs) if qs.size > 0 else np.array([], dtype=np.float64)

                # bucket counts
                bucket_tot = np.zeros(k, dtype=np.int64)
                bucket_rev = np.zeros(k, dtype=np.int64)

                for e in summaries:
                    v = e.start_volatility
                    if not np.isfinite(v):
                        continue
                    b = int(np.searchsorted(cuts, v, side="right"))
                    if b < 0:
                        b = 0
                    elif b >= k:
                        b = k - 1
                    bucket_tot[b] += 1
                    if e.status == EventStatus.REVERTED:
                        bucket_rev[b] += 1

                by_vol = {}
                for i in range(k):
                    if bucket_tot[i] == 0:
                        by_vol[f"bucket_{i}"] = (0.0 if scoring_cfg.record_empty_scores else float("nan"))
                    else:
                        by_vol[f"bucket_{i}"] = float(bucket_rev[i] / bucket_tot[i])

        return ScoreResult(
            score=float(score),
            total_events=total,
            reverted_events=reverted,
            failed_events=failed,
            expired_events=expired,
            by_direction=by_dir,
            by_volatility_bucket=by_vol,
            events=summaries if self.config.diagnostics.enabled else None,
        )
