"""Strategy registry: @register, auto-discovery of strategies/*.py, entry points, 'module:Class'."""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path

from .base import Strategy

_REG: dict[str, type[Strategy]] = {}
_DISCOVERED: set[str] = set()


def register(cls: type[Strategy]) -> type[Strategy]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty `name`")
    _REG[cls.name] = cls
    return cls


def unregister(name: str) -> None:
    _REG.pop(name, None)


def default_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[3]
    dirs = [root / "strategies", Path.cwd() / "strategies"]
    for p in os.environ.get("TRADELAB_STRATEGIES", "").split(os.pathsep):
        if p:
            dirs.append(Path(p))
    seen, out = set(), []
    for d in dirs:
        r = d.resolve()
        if r.is_dir() and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def load_file(path: Path) -> None:
    key = str(path.resolve())
    if key in _DISCOVERED:
        return
    mod_name = f"tradelab_user_{path.stem}_{abs(hash(key)) % 10**8}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _DISCOVERED.add(key)


def discover(extra: list[str | Path] | None = None) -> None:
    for d in default_dirs() + [Path(p) for p in (extra or [])]:
        files = sorted(d.glob("*.py")) if d.is_dir() else ([d] if d.is_file() else [])
        for f in files:
            if f.name.startswith("_"):
                continue
            load_file(f)
    try:
        from importlib.metadata import entry_points

        for ep in entry_points(group="tradelab.strategies"):
            obj = ep.load()
            if isinstance(obj, type) and issubclass(obj, Strategy):
                register(obj)
    except Exception:  # pragma: no cover
        pass


def get_strategy(name: str, extra: list[str | Path] | None = None) -> type[Strategy]:
    if ":" in name:
        mod, cls = name.split(":", 1)
        return getattr(importlib.import_module(mod), cls)
    if name not in _REG:
        discover(extra)
    if name not in _REG:
        raise KeyError(f"unknown strategy {name!r}; registered: {sorted(_REG)}")
    return _REG[name]


def list_strategies(extra=None) -> dict[str, type[Strategy]]:
    discover(extra)
    return dict(sorted(_REG.items()))
