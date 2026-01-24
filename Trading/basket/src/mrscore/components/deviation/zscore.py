from __future__ import annotations

from mrscore.core.results import Direction


class ZScoreDeviationDetector:
    """
    Detect a deviation event when:
      - abs(z) >= threshold
      - abs_move >= min_absolute_move

    Direction convention (aligned with core.results.Direction):
      - z >= +threshold => DOWN (price above mean; bet on reversion down)
      - z <= -threshold => UP   (price below mean; bet on reversion up)
    """

    def __init__(self, *, threshold: float, min_absolute_move: float) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        if min_absolute_move < 0:
            raise ValueError("min_absolute_move must be >= 0")
        self.threshold = float(threshold)
        self.min_absolute_move = float(min_absolute_move)

    def detect(self, *, price: float, mean: float, volatility: float) -> Direction | None:
        vol = float(volatility)
        if vol <= 0.0:
            return None

        p = float(price)
        m = float(mean)
        move = p - m

        # absolute move filter
        if abs(move) < self.min_absolute_move:
            return None

        z = move / vol
        if abs(z) < self.threshold:
            return None

        return Direction.DOWN if z > 0.0 else Direction.UP
