from __future__ import annotations

from typing import Dict, Iterable, Optional, Protocol

import numpy as np

from mrscore.config.models import DiagnosticsConfig, ScoringConfig
from mrscore.core.results import Direction, EventStatus, EventSummary, ScoreResult


class Scorer(Protocol):
    def score(self, *args, **kwargs):
        raise NotImplementedError


def score_events(
    *,
    events: Iterable[EventSummary],
    scoring: ScoringConfig,
    diagnostics: DiagnosticsConfig,
) -> ScoreResult:
    summaries = list(events)

    total = len(summaries)
    reverted = sum(1 for e in summaries if e.status == EventStatus.REVERTED)
    failed = sum(1 for e in summaries if e.status == EventStatus.FAILED)
    expired = sum(1 for e in summaries if e.status == EventStatus.EXPIRED)

    if total == 0 and not scoring.record_empty_scores:
        score = float("nan")
    else:
        score = (reverted / total) if total > 0 else 0.0

    by_dir: Optional[Dict[str, float]] = None
    if scoring.by_direction:
        up_total = sum(1 for e in summaries if e.direction == Direction.UP)
        dn_total = total - up_total
        up_rev = sum(1 for e in summaries if e.direction == Direction.UP and e.status == EventStatus.REVERTED)
        dn_rev = sum(1 for e in summaries if e.direction == Direction.DOWN and e.status == EventStatus.REVERTED)

        def _ratio(a: int, b: int) -> float:
            if b == 0:
                return float("nan") if not scoring.record_empty_scores else 0.0
            return a / b

        by_dir = {
            Direction.UP.value: _ratio(up_rev, up_total),
            Direction.DOWN.value: _ratio(dn_rev, dn_total),
        }

    by_vol: Optional[Dict[str, float]] = None
    if scoring.by_volatility_bucket:
        k = int(scoring.volatility_buckets or 0)
        if k <= 0:
            raise ValueError("volatility_buckets must be set when by_volatility_bucket is true")

        vols = np.array([e.start_volatility for e in summaries], dtype=np.float64)
        vols = vols[np.isfinite(vols)]
        if vols.size == 0:
            by_vol = {f"bucket_{i}": (0.0 if scoring.record_empty_scores else float("nan")) for i in range(k)}
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
                    by_vol[f"bucket_{i}"] = (0.0 if scoring.record_empty_scores else float("nan"))
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
        events=summaries if diagnostics.enabled else None,
    )
