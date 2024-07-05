from __future__ import annotations

from Trading.utils.criterion.enableable import Enableable
from Trading.utils.operator import OPERATOR_TO_SYMBOL
from typing import Optional
import operator


class Expression(Enableable):
    def __init__(
        self, name: str, op: operator, left, right, is_enaled: bool = True
    ) -> None:
        self.name = name
        self.left = left
        self.right = right
        self.operator = op

        Enableable.__init__(self, is_enaled)

        if left is None or right is None:
            return

    def __str__(self) -> str:
        left = self.left
        right = self.right
        if left is None:
            left = "X"
        if right is None:
            right = "X"
        if isinstance(left, float):
            left = round(self.left, 2)
        if isinstance(right, float):
            right = round(right, 2)
        left, right = str(left), str(right)
        operator_symbol = OPERATOR_TO_SYMBOL[self.operator]
        evaluate = str(self.evaluate())
        s = f"({self.name}{left} {operator_symbol} {right} {evaluate})"
        return s

    def formatted(self):
        s = str(self)
        parts = s.split("&")
        formatted_parts = [part.strip() for part in parts]
        formatted_text = " & \n".join(formatted_parts)
        parts = formatted_text.split("|")
        formatted_parts = [part.strip() for part in parts]
        formatted_text = " | \n".join(formatted_parts)
        return formatted_text

    def evaluate(self) -> bool:
        if self.left is None or self.right is None:
            return False
        return self.operator(self.left.evaluate(), self.right.evaluate())

    def __or__(self, other) -> Expression:
        if not self.is_enabled:
            return other
        if not other.is_enabled:
            return self
        return Expression("", operator.or_, left=self, right=other)

    def __and__(self, other) -> Expression:
        if not self.is_enabled:
            return other
        if not other.is_enabled:
            return self
        return Expression("", operator.and_, self, other)

    def debug(self):
        """
        Find the first expression that evaluates to False
        """
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

NUMERICAL = float | int
class Numerical(Expression):
    def __init__(
        self,
        name: str,
        op: operator,
        left: Optional[NUMERICAL] = None,
        right: Optional[NUMERICAL] = None,
    ) -> None:
        Expression.__init__(self, name, op, left, right)

    def evaluate(self) -> bool:
        if self.left is None or self.right is None:
            return False
        return self.operator(self.left, self.right)

    def debug(self):
        if self.evaluate():
            return
        return self


class Threshold(Numerical):
    def __init__(self, name: str, op: operator, threshold: NUMERICAL) -> None:
        super().__init__(name, op, right=threshold)

    @property
    def value(self):
        return self.left

    @value.setter
    def value(self, value):
        self.left = value


def and_(*criteria) -> Expression:
    c = criteria[0]
    return c & and_(*criteria[1:]) if criteria[1:] else c


def or_(*criteria) -> Expression:
    c = criteria[0]
    return c | or_(*criteria[1:]) if criteria[1:] else c
