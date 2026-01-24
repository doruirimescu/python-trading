from __future__ import annotations


class EWMA:
    def __init__(self, *, window: int, min_volatility: float, volatility_unit: str) -> None:
        self.window = window
        self.min_volatility = min_volatility
        self.volatility_unit = volatility_unit
