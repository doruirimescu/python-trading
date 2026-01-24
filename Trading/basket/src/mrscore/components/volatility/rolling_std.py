from __future__ import annotations

import numpy as np


class RollingStd:
    """
    Rolling standard deviation over a fixed window using a ring buffer.

    Intended for returns volatility (unit = returns). O(1) update.
    """

    def __init__(
        self,
        *,
        window: int,
        min_periods: int = 1,
        ddof: int = 0,
        min_volatility: float = 0.0,
    ) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        if min_periods < 1:
            raise ValueError("min_periods must be >= 1")
        if min_periods > window:
            raise ValueError("min_periods must be <= window")
        if ddof not in (0, 1):
            raise ValueError("ddof must be 0 or 1")
        if min_volatility < 0:
            raise ValueError("min_volatility must be >= 0")

        self._window = int(window)
        self._min_periods = int(min_periods)
        self._ddof = int(ddof)
        self._min_vol = float(min_volatility)

        self._buf = np.zeros(self._window, dtype=np.float64)
        self._idx = 0
        self._count = 0
        self._sum = 0.0
        self._sumsq = 0.0

        self.value = 0.0

    def reset(self) -> None:
        self._buf.fill(0.0)
        self._idx = 0
        self._count = 0
        self._sum = 0.0
        self._sumsq = 0.0
        self.value = 0.0

    def is_ready(self) -> bool:
        return self._count >= self._min_periods

    def update(self, r: float) -> float:
        x = float(r)

        if self._count >= self._window:
            outgoing = float(self._buf[self._idx])
            self._sum -= outgoing
            self._sumsq -= outgoing * outgoing
        else:
            self._count += 1

        self._buf[self._idx] = x
        self._sum += x
        self._sumsq += x * x

        self._idx += 1
        if self._idx == self._window:
            self._idx = 0

        n = self._count
        denom = n - self._ddof
        if denom <= 0:
            self.value = max(self._min_vol, 0.0)
            return self.value

        mean = self._sum / n
        var = (self._sumsq - n * mean * mean) / denom
        if var < 0.0:
            var = 0.0

        vol = var ** 0.5
        self.value = vol if vol >= self._min_vol else self._min_vol
        return self.value
