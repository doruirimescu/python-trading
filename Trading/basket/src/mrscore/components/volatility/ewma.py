from __future__ import annotations


class EWMAVol:
    """
    EWMA volatility on returns.

    Updates variance via:
      sigma2_t = lam*sigma2_{t-1} + (1-lam)*r_t^2

    Where lam is derived from span:
      alpha = 2/(span+1)
      lam = 1 - alpha

    Warm-up:
      - Until min_periods reached, uses running mean of r^2.
    """

    def __init__(
        self,
        *,
        span: int,
        min_periods: int = 1,
        min_volatility: float = 0.0,
    ) -> None:
        if span < 1:
            raise ValueError("span must be >= 1")
        if min_periods < 1:
            raise ValueError("min_periods must be >= 1")
        if min_volatility < 0:
            raise ValueError("min_volatility must be >= 0")

        self._span = int(span)
        alpha = 2.0 / (self._span + 1.0)
        self._lam = 1.0 - alpha

        self._min_periods = int(min_periods)
        self._min_vol = float(min_volatility)

        self._count = 0
        self._running_sumsq = 0.0
        self._sigma2 = 0.0
        self._initialized = False

        self.value = 0.0

    def reset(self) -> None:
        self._count = 0
        self._running_sumsq = 0.0
        self._sigma2 = 0.0
        self._initialized = False
        self.value = 0.0

    def is_ready(self) -> bool:
        return self._count >= self._min_periods

    def update(self, r: float) -> float:
        x = float(r)
        self._count += 1
        x2 = x * x

        # Warm-up: running mean of r^2
        if not self._initialized:
            self._running_sumsq += x2
            self._sigma2 = self._running_sumsq / self._count
            self.value = (self._sigma2 ** 0.5)
            if self._count >= self._min_periods:
                self._initialized = True
            if self.value < self._min_vol:
                self.value = self._min_vol
            return self.value

        # EWMA recursion
        self._sigma2 = self._lam * self._sigma2 + (1.0 - self._lam) * x2
        vol = self._sigma2 ** 0.5
        self.value = vol if vol >= self._min_vol else self._min_vol
        return self.value
