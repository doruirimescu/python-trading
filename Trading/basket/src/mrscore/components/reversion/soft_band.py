from __future__ import annotations


class SoftBandReversionCriteria:
    """Reverted when abs(zscore) <= z_tolerance."""

    def __init__(self, *, z_tolerance: float) -> None:
        if z_tolerance <= 0:
            raise ValueError("z_tolerance must be > 0")
        self.z_tolerance = float(z_tolerance)

    def is_reverted(self, *, zscore: float) -> bool:
        return abs(float(zscore)) <= self.z_tolerance
