from __future__ import annotations


class GARCH11Vol:
    """
    GARCH(1,1) conditional volatility on returns:

      sigma2_t = omega + alpha * r_{t-1}^2 + beta * sigma2_{t-1}

    Notes:
    - Still O(1) update.
    - Requires reasonable parameters; typical constraints:
        omega > 0, alpha >= 0, beta >= 0, alpha + beta < 1

    Warm-up:
    - For the first observation, sigma2 initializes to init_sigma2 if provided,
      otherwise to r^2 (bounded by min_volatility^2).
    """

    def __init__(
        self,
        *,
        omega: float,
        alpha: float,
        beta: float,
        init_sigma2: float | None = None,
        min_volatility: float = 0.0,
        min_periods: int = 1,
        enforce_stationarity: bool = True,
    ) -> None:
        if omega <= 0:
            raise ValueError("omega must be > 0")
        if alpha < 0 or beta < 0:
            raise ValueError("alpha and beta must be >= 0")
        if min_periods < 1:
            raise ValueError("min_periods must be >= 1")
        if min_volatility < 0:
            raise ValueError("min_volatility must be >= 0")
        if init_sigma2 is not None and init_sigma2 <= 0:
            raise ValueError("init_sigma2 must be > 0")

        if enforce_stationarity and (alpha + beta) >= 1.0:
            raise ValueError("Stationarity requires alpha + beta < 1")

        self._omega = float(omega)
        self._alpha = float(alpha)
        self._beta = float(beta)
        self._min_vol = float(min_volatility)
        self._min_periods = int(min_periods)

        self._count = 0
        self._sigma2 = float(init_sigma2) if init_sigma2 is not None else 0.0
        self.value = 0.0

        self._initialized = init_sigma2 is not None

    def reset(self) -> None:
        # Deterministic reset to a neutral state
        self._count = 0
        self._sigma2 = 0.0
        self.value = 0.0
        self._initialized = False

    def is_ready(self) -> bool:
        return self._count >= self._min_periods

    def update(self, r: float) -> float:
        x = float(r)
        x2 = x * x
        self._count += 1

        min_sigma2 = self._min_vol * self._min_vol

        if not self._initialized:
            self._sigma2 = x2 if x2 > min_sigma2 else min_sigma2
            self._initialized = True
        else:
            self._sigma2 = self._omega + self._alpha * x2 + self._beta * self._sigma2
            if self._sigma2 < min_sigma2:
                self._sigma2 = min_sigma2

        vol = self._sigma2 ** 0.5
        self.value = vol
        return self.value
