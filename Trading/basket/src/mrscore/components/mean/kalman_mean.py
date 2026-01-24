# components/mean/kalman_mean.py
from __future__ import annotations


class KalmanMean:
    """
    1D Kalman filter estimating a latent mean level.

    Model (constant level with process noise):
      x_t = x_{t-1} + w_t,  w_t ~ N(0, q)
      y_t = x_t + v_t,      v_t ~ N(0, r)

    Pros:
    - Adapts smoothly in regime shifts
    - Provides an implicit "confidence" via variance (P)
    - Very useful for experimental research / regime classification

    Parameters:
    - process_var (q): how quickly the mean is allowed to move
    - obs_var (r): observation noise level
    - init_mean: initial state
    - init_var: initial uncertainty
    - min_periods: warm-up gate for is_ready
    """

    def __init__(
        self,
        *,
        process_var: float,
        obs_var: float,
        init_mean: float = 0.0,
        init_var: float = 1.0,
        min_periods: int = 1,
    ) -> None:
        if process_var <= 0:
            raise ValueError("process_var must be > 0")
        if obs_var <= 0:
            raise ValueError("obs_var must be > 0")
        if init_var <= 0:
            raise ValueError("init_var must be > 0")
        if min_periods < 1:
            raise ValueError("min_periods must be >= 1")

        self._q = float(process_var)
        self._r = float(obs_var)
        self._min_periods = int(min_periods)

        self._count = 0
        self.value = float(init_mean)   # state estimate x
        self._P = float(init_var)       # state variance

    def reset(self) -> None:
        # For deterministic resets, users should re-instantiate if they want specific init values
        self._count = 0
        self.value = 0.0
        self._P = 1.0

    def is_ready(self) -> bool:
        return self._count >= self._min_periods

    @property
    def variance(self) -> float:
        """Current state variance (uncertainty)."""
        return self._P

    def update(self, price: float) -> float:
        y = float(price)
        self._count += 1

        # Predict
        P_pred = self._P + self._q
        x_pred = self.value

        # Update
        S = P_pred + self._r          # innovation variance
        K = P_pred / S                # Kalman gain
        self.value = x_pred + K * (y - x_pred)
        self._P = (1.0 - K) * P_pred

        return self.value
