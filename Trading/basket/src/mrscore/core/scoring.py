from __future__ import annotations

from typing import Protocol


class Scorer(Protocol):
    def score(self, *args, **kwargs):
        raise NotImplementedError
