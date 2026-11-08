"""Wall-clock access is isolated here (run ids only). Never use in strategy/engine logic."""
from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def run_stamp() -> str:
    return now_utc().strftime("%Y%m%d-%H%M%S")
