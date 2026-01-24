from __future__ import annotations


class CompositeFailureCriteria:
    def __init__(self, *, max_duration: int | None, max_zscore: float | None) -> None:
        if max_duration is not None and max_duration <= 0:
            raise ValueError("max_duration must be > 0")
        if max_zscore is not None and max_zscore <= 0:
            raise ValueError("max_zscore must be > 0")
        if max_duration is None and max_zscore is None:
            raise ValueError("At least one of max_duration or max_zscore must be set")
        self.max_duration = max_duration
        self.max_zscore = max_zscore

    def is_failed(self, *, duration: int, zscore: float) -> bool:
        d = int(duration)
        z = float(zscore)

        if self.max_duration is not None and d >= self.max_duration:
            return True
        if self.max_zscore is not None and abs(z) >= self.max_zscore:
            return True
        return False
