from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import operator
from Trading.utils.operator import OPERATOR_TO_SYMBOL

@dataclass
class Numeric:
    name: str
    operator: operator
    left: float | int
    right: float | int
    _is_enabled: bool = True

    def __str__(self) -> str:
        if isinstance(self.left, float):
            self.left = round(self.left, 2)
        if isinstance(self.right, float):
            self.right = round(self.right, 2)
        s = "(" + self.name + str(self.left) + " " + OPERATOR_TO_SYMBOL[self.operator] + " " + str(self.right) +  " " + str(self.evaluate()) + ")"
        return s

    def evaluate(self) -> bool:
        return self.operator(self.left, self.right)

@dataclass
class Criterion:
    name: str
    operator: operator
    left: float | int | Criterion
    right: float | int | Criterion
    _is_enabled: bool = True

    def __str__(self) -> str:
        if isinstance(self.left, float):
            self.left = round(self.left, 2)
        if isinstance(self.right, float):
            self.right = round(self.right, 2)
        s = "(" + self.name + str(self.left) + " " + OPERATOR_TO_SYMBOL[self.operator] + " " + str(self.right) +  " " + str(self.evaluate()) + ")"
        return s

    def __post_init__(self):
        if self.name:
            self.name = f"{self.name}: "

        if isinstance(self.left, float | int) and isinstance(self.right, float | int):
            pass
        elif isinstance(self.left, Criterion) and isinstance(self.left, Criterion):
            pass
        else:
            raise ValueError(f"Invalid type for left {type(self.left)} and right arguments")

    def evaluate(self) -> bool:
        if isinstance(self.left, float | int) and isinstance(self.right, float | int):
            return self.operator(self.left, self.right)
        elif isinstance(self.left, Criterion) and isinstance(self.left, Criterion):
            return self.operator(self.left.evaluate(), self.right.evaluate())
        else:
            raise ValueError(f"Invalid type for left {type(self.left)} and right arguments")

    def __or__(self, other: Criterion) -> Criterion:
        if not self._is_enabled:
            return other
        if not other._is_enabled:
            return self
        return Criterion("", operator.or_, self, other)

    def __and__(self, other: Criterion) -> Criterion:
        if not self._is_enabled:
            return other
        if not other._is_enabled:
            return self
        return Criterion("", operator.and_, self, other)

    def enable(self):
        self._is_enabled = True

    def disable(self):
        self._is_enabled = False

    def formatted(self):
        s = str(self)
        parts = s.split('&')
        formatted_parts = [part.strip() for part in parts]
        formatted_text = " & \n".join(formatted_parts)
        parts = formatted_text.split('|')
        formatted_parts = [part.strip() for part in parts]
        formatted_text = " | \n".join(formatted_parts)
        return formatted_text

    def debug(self):
        if self.evaluate():
            return

        if isinstance(self.left, float | int):
            return self

        if self.operator == operator.and_:
            if not self.left.evaluate():
                return self.left.debug()
            elif not self.right.evaluate():
                return self.right.debug()
        elif self.operator == operator.or_:
            return self.left.debug()
        elif self.operator == operator.__eq__:
            return self.left.debug()
        elif self.operator == operator.__ne__:
            return self.left.debug()

def and_criteria(*criteria) -> Criterion:
    c = criteria[0]
    return c & and_criteria(*criteria[1:]) if criteria[1:] else c

def or_criteria(*criteria) -> Criterion:
    c = criteria[0]
    return c | or_criteria(*criteria[1:]) if criteria[1:] else c

c_1 = Criterion("Return on Equity", operator.ge, 10.0, 0.5)
c_2 = Criterion("Debt to Equity", operator.ge, 0.5, 1.0)
c_3 = Criterion("Return on Equity", operator.ge, 10.0, 100.0)
c_4 = Criterion("Debt to Equity", operator.le, 0.5, 200.0)

c= and_criteria(c_1, c_2)
d= or_criteria(c_3, c_4)
print(c)
print(d)
e = c & d
print(e)

print("+++++")
print(e.debug())
