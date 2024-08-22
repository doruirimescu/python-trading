from __future__ import annotations

from Trading.utils.criterion.enableable import Enableable
from Trading.utils.operator_util import OPERATOR_TO_SYMBOL
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
        if self.left and isinstance(self.left, Enableable) and not self.left.is_enabled:
            return str(self.right)
        if self.right and isinstance(self.right, Enableable) and not self.right.is_enabled:
            return str(self.left)
        s = f"({self.name} {left} {operator_symbol} {right} {evaluate})"
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
        if not self.is_enabled:
            return True
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
        if not self.is_enabled:
            return True
        return self.operator(self.left, self.right)

    def debug(self):
        if self.evaluate():
            return
        return self


class Threshold(Numerical):
    '''
    A threshold is a numerical expression with a name and an operator, used
    to compare a value with a threshold
    '''
    def __init__(self, name: str, op: operator, threshold: NUMERICAL) -> None:
        super().__init__(name, op, right=threshold)

    @property
    def value(self):
        return self.left

    @value.setter
    def value(self, value):
        self.left = value

class ThresholdGE(Threshold):
    def __init__(self, name: str, threshold: NUMERICAL) -> None:
        super().__init__(name, operator.ge, threshold)

class ThresholdGT(Threshold):
    def __init__(self, name: str, threshold: NUMERICAL) -> None:
        super().__init__(name, operator.gt, threshold)

class ThresholdLE(Threshold):
    def __init__(self, name: str, threshold: NUMERICAL) -> None:
        super().__init__(name, operator.le, threshold)

class ThresholdLT(Threshold):
    def __init__(self, name: str, threshold: NUMERICAL) -> None:
        super().__init__(name, operator.lt, threshold)

def and_(*criteria) -> Expression:
    c = criteria[0]
    return c & and_(*criteria[1:]) if criteria[1:] else c


def or_(*criteria) -> Expression:
    c = criteria[0]
    return c | or_(*criteria[1:]) if criteria[1:] else c

# roe = Threshold("Return on Equity: ", operator.ge, 10.0)
# print(roe)
# div_yield = Threshold("Dividend yield: ", operator.ge, 5.0)
# print(div_yield)
# combined = roe & div_yield
# print(combined)

# roe.value = 15.0
# div_yield.value = 7.0
# print(combined)

# roe.value = 3.0
# print(combined.debug())

# roe.disable()
# print(combined)
