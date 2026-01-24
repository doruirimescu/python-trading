from __future__ import annotations


class CompositeFailureCriteria:
    def __init__(self, *, max_duration: int | None, max_zscore: float | None) -> None:
        self.max_duration = max_duration
        self.max_zscore = max_zscore
