from __future__ import annotations


class ZScoreDeviationDetector:
    def __init__(self, *, threshold: float, min_absolute_move: float) -> None:
        self.threshold = threshold
        self.min_absolute_move = min_absolute_move
