"""Stable hashing helpers (sha256 of canonical JSON, DataFrame fingerprints)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd


def _default(o: Any):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if hasattr(o, "model_dump"):
        return o.model_dump()
    return str(o)


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=_default, separators=(",", ":"))


def stable_hash(obj: Any, n: int | None = None) -> str:
    h = hashlib.sha256(stable_json(obj).encode()).hexdigest()
    return h[:n] if n else h


def frame_fingerprint(df: pd.DataFrame, n: int = 16) -> str:
    """Hash index + values of a DataFrame (order-sensitive)."""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
    h.update(str(list(df.columns)).encode())
    return h.hexdigest()[:n]
