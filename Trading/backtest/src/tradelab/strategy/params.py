"""Strategy parameters: pydantic models with grid hints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


def grid(default, *, low=None, high=None, step=None, values=None, description: str = "", **kw):
    """Field with optimisation hints: grid(10, low=5, high=50, step=5) or grid(10, values=[5,10,20])."""
    extra: dict[str, Any] = {"grid": {k: v for k, v in dict(low=low, high=high, step=step, values=values).items() if v is not None}}
    return Field(default, description=description, json_schema_extra=extra, **kw)


def grid_axes(params_cls: type[Params]) -> dict[str, list]:
    """Candidate values per parameter from `grid(...)` hints (used by robustness/optimize)."""
    out: dict[str, list] = {}
    for name, f in params_cls.model_fields.items():
        g = (f.json_schema_extra or {}).get("grid") if isinstance(f.json_schema_extra, dict) else None
        if not g:
            continue
        if "values" in g:
            out[name] = list(g["values"])
        elif "low" in g and "high" in g:
            step = g.get("step") or (g["high"] - g["low"])
            vals, v = [], g["low"]
            while v <= g["high"] + 1e-12:
                vals.append(type(f.default)(v) if isinstance(f.default, int) else v)
                v += step
            out[name] = vals
    return out
