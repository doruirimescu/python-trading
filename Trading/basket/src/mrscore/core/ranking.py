# mrscore/core/ranking.py
from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Any, Optional

from mrscore.core.ratio_universe import RatioJob


@dataclass(frozen=True)
class RankedJob:
    job: RatioJob
    score: float
    meta: Optional[dict[str, Any]] = None


class TopKRanker:
    """
    Keep top-k items by score using a min-heap.

    - consider(): O(log k)
    - items_sorted(): O(k log k)
    - Does not allocate per item beyond heap nodes.
    """

    def __init__(self, k: int) -> None:
        if k < 1:
            raise ValueError("k must be >= 1")
        self._k = int(k)
        self._heap: list[tuple[float, int, RankedJob]] = []
        self._tie = 0  # deterministic tie-breaker

    @property
    def k(self) -> int:
        return self._k

    def __len__(self) -> int:
        return len(self._heap)

    def consider(self, *, job: RatioJob, score: float, meta: Optional[dict[str, Any]] = None) -> None:
        s = float(score)
        item = RankedJob(job=job, score=s, meta=meta)

        # Push until full; then replace smallest if better
        if len(self._heap) < self._k:
            heapq.heappush(self._heap, (s, self._tie, item))
            self._tie += 1
            return

        # If not better than current worst, skip
        if s <= self._heap[0][0]:
            return

        heapq.heapreplace(self._heap, (s, self._tie, item))
        self._tie += 1

    def items_sorted(self, *, descending: bool = True) -> list[RankedJob]:
        items = [node[2] for node in self._heap]
        items.sort(key=lambda x: x.score, reverse=descending)
        return items

    def jobs_sorted(self, *, descending: bool = True) -> list[RatioJob]:
        return [r.job for r in self.items_sorted(descending=descending)]
