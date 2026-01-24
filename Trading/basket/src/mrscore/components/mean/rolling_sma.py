from __future__ import annotations


class RollingSMA:
    def __init__(self, *, window: int) -> None:
        self.window = window
