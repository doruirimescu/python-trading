from __future__ import annotations


class SoftBandReversionCriteria:
    def __init__(self, *, z_tolerance: float) -> None:
        self.z_tolerance = z_tolerance
