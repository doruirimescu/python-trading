"""Deterministic seeding via SeedSequence."""
from __future__ import annotations

import hashlib

import numpy as np


def _key(*parts) -> int:
    s = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "little")


def rng_for(seed: int, *parts) -> np.random.Generator:
    """Independent, reproducible generator for (seed, *parts)."""
    return np.random.default_rng(np.random.SeedSequence([int(seed) & 0xFFFFFFFF, _key(*parts) & 0xFFFFFFFF]))
