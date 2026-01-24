# components/mean/ema.py
from __future__ import annotations


class EMA:
    """
    Exponential moving average (EWMA mean).

    Pros:
    - O(1) update
    - Minimal state
    - Adapts quickly to regime changes
    - Production-friendly (fast, stable)

    Parameters:
    - span: standard finance convention, alpha = 2/(span+1)
    - min_periods: warm-up; until reached, EMA will behave as simple running mean
    """

    def __init__(self, *, span: int, min_periods: int = 1) -> None:
        if span < 1:
            raise ValueError("span must be >= 1")
        if min_periods < 1:
            raise ValueError("min_periods must be >= 1")

        self._span = int(span)
        self._alpha = 2.0 / (self._span + 1.0)
        self._min_periods = int(min_periods)

        self._count = 0
        self._running_sum = 0.0
        self.value = 0.0
        self._initialized = False

    def reset(self) -> None:
        self._count = 0
        self._running_sum = 0.0
        self.value = 0.0
        self._initialized = False

    def is_ready(self) -> bool:
        return self._count >= self._min_periods

    def update(self, price: float) -> float:
        x = float(price)
        self._count += 1

        # Warm-up: use running mean until min_periods reached
        if not self._initialized:
            self._running_sum += x
            self.value = self._running_sum / self._count
            if self._count >= self._min_periods:
                # initialize EMA state at the warm-up mean
                self._initialized = True
            return self.value

        # EMA recursion
        self.value = self._alpha * x + (1.0 - self._alpha) * self.value
        return self.value
