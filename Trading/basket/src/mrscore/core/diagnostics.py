from __future__ import annotations

from typing import Protocol


class DiagnosticsCollector(Protocol):
    def record(self, *args, **kwargs):
        raise NotImplementedError
