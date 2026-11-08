"""Pure fill-resolution helpers (unit-testable)."""
from __future__ import annotations

import math



def round_tick(px: float, tick: float, mode: str = "nearest") -> float:
    """Round to the tick grid. mode: nearest | up | down (adverse rounding of order prices uses up/down)."""
    if not tick or tick <= 0 or px is None or px != px:
        return px
    q = px / tick
    if mode == "up":
        k = math.ceil(q - 1e-9)
    elif mode == "down":
        k = math.floor(q + 1e-9)
    else:
        k = round(q)
    return round(k * tick, 10)


def _reach_below(low: float, price: float, tick: float, through: bool) -> bool:
    """Did `low` trade at/through `price`? through: needs one full tick beyond (strictly beyond when tick == 0)."""
    if not through:
        return low <= price
    if tick and tick > 0:
        return low <= price - tick + 1e-9 * tick
    return low < price


def _reach_above(high: float, price: float, tick: float, through: bool) -> bool:
    if not through:
        return high >= price
    if tick and tick > 0:
        return high >= price + tick - 1e-9 * tick
    return high > price


def resolve_bracket(direction: int, o: float, h: float, l: float, stop: float | None, target: float | None,
                    *, held_at_open: bool, intrabar: str = "conservative", tick: float = 0.0, through: bool = False):
    """Decide if/where a stop/target bracket exits within one bar.

    direction: +1 long, -1 short. held_at_open: position existed before the bar's open (gap rules apply).
    through: the target is a resting LIMIT order and needs a trade one tick through it (stops trigger on touch).
    Returns (reason, price) or None.
      - stop gapped through at the open -> fill at the open (worse than stop)
      - target gapped through at the open -> fill at the open (better than target)
      - both touched inside the bar -> stop (conservative) / target (optimistic)
    """
    if direction > 0:
        if held_at_open:
            if stop is not None and o <= stop:
                return "stop", o
            if target is not None and _reach_above(o, target, tick, through):
                return "target", o
        s_hit = stop is not None and l <= stop
        t_hit = target is not None and _reach_above(h, target, tick, through)
    else:
        if held_at_open:
            if stop is not None and o >= stop:
                return "stop", o
            if target is not None and _reach_below(o, target, tick, through):
                return "target", o
        s_hit = stop is not None and h >= stop
        t_hit = target is not None and _reach_below(l, target, tick, through)
    if s_hit and t_hit:
        return ("stop", stop) if intrabar == "conservative" else ("target", target)
    if s_hit:
        return "stop", stop
    if t_hit:
        return "target", target
    return None


def resolve_entry(side: int, kind: str, price: float | None, o: float, h: float, l: float, *, tick: float = 0.0,
                  through: bool = False):
    """Entry fill for a working order within a bar: returns (fill_price, is_stop_type) or None.

    market: open. limit: touch (or `through`: one tick beyond) -> fill at price (or open if gapped through, better).
    stop: trigger on touch -> fill at price (or open if gapped through, worse).
    """
    if kind == "market":
        return o, False
    if kind == "limit":
        if side > 0 and _reach_below(l, price, tick, through):
            return min(o, price), False
        if side < 0 and _reach_above(h, price, tick, through):
            return max(o, price), False
        return None
    if kind == "stop":
        if side > 0 and h >= price:
            return max(o, price), True
        if side < 0 and l <= price:
            return min(o, price), True
        return None
    raise ValueError(kind)
