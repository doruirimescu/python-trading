from __future__ import annotations

from mrscore.core.results import Direction


class ZScoreDeviationDetector:
    def __init__(self, *, threshold: float, min_absolute_move: float) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        if min_absolute_move < 0:
            raise ValueError("min_absolute_move must be >= 0")
        self.threshold = float(threshold)
        self.min_absolute_move = float(min_absolute_move)

    def detect(self, *, price: float, mean: float, volatility: float) -> Direction | None:
        """
        Returns a Direction if deviation is large enough, else None.

        Conditions:
          - abs(z) >= threshold
          - abs(price - mean) >= min_absolute_move
        """
        vol = float(volatility)
        if vol <= 0.0:
            return None

        p = float(price)
        m = float(mean)
        move = p - m
        if abs(move) < self.min_absolute_move:
            return None

        z = move / vol
        if abs(z) < self.threshold:
            return None

        return Direction.UP if z > 0.0 else Direction.DOWN
