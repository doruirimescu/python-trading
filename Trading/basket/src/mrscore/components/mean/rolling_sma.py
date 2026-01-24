# components/mean/rolling_sma.py
from __future__ import annotations

import numpy as np


class RollingSMA:
    """
    Rolling simple moving average using a fixed-size ring buffer.

    Design goals:
    - O(1) update
    - No allocations in the hot loop
    - Deterministic, causal
    """

    def __init__(self, *, window: int) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self._window = int(window)
        self._buf = np.zeros(self._window, dtype=np.float64)
        self._idx = 0
        self._count = 0
        self._sum = 0.0
        self.value = 0.0

    def reset(self) -> None:
        self._buf.fill(0.0)
        self._idx = 0
        self._count = 0
        self._sum = 0.0
        self.value = 0.0

    def is_ready(self) -> bool:
        return self._count >= self._window

    def update(self, price: float) -> float:
        x = float(price)

        # remove outgoing element if buffer is full
        if self._count >= self._window:
            outgoing = float(self._buf[self._idx])
            self._sum -= outgoing
        else:
            self._count += 1

        # add incoming
        self._buf[self._idx] = x
        self._sum += x

        # advance ring index
        self._idx += 1
        if self._idx == self._window:
            self._idx = 0

        # compute mean over available samples (warm-up uses count)
        self.value = self._sum / self._count
        return self.value
