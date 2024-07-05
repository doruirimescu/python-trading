from unittest import TestCase
import operator
from Trading.utils.criterion.expression import Threshold, Numerical, and_, or_

class TestExpression(TestCase):
    def test_expression_evaluate(self):
        roe_expression = Threshold("Roe", operator.ge, 10.0)
        self.assertFalse(roe_expression.evaluate())
        roe_expression.value = 10.0
        self.assertTrue(roe_expression.evaluate())

    def test_expression_and(self):
        e_1 = Numerical("e_1", operator.ge, 10.0, 10.0)
        e_2 = Numerical("e_2", operator.lt, 10.0, 20.0)
        e_3 = Numerical("e_3", operator.eq, 10.0, 5.0)
        r = and_(e_1, e_2, e_3)
        self.assertFalse(r.evaluate())
        e_3.right = 10.0
        self.assertTrue(r.evaluate())

    def test_expression_or(self):
        e_1 = Numerical("e_1", operator.ge, 10.0, 10.0)
        e_2 = Numerical("e_2", operator.lt, 10.0, 20.0)
        r = or_(e_1, e_2)
        self.assertTrue(r.evaluate())
        e_1.left = 5.0
        self.assertTrue(r.evaluate())
        e_2.right = 5.0
        self.assertFalse(r.evaluate())

    def test_expression_str(self):
        roe_expression = Threshold("Return on Equity: ", operator.ge, 10.0)
        self.assertEqual(str(roe_expression), "(Return on Equity: X >= 10.0 False)")
        roe_expression.value = 10.0
        self.assertEqual(str(roe_expression), "(Return on Equity: 10.0 >= 10.0 True)")

        e_1 = Numerical("e_1: ", operator.ge, 10.0, 10.0)
        e_2 = Numerical("e_2: ", operator.lt, 10.0, 20.0)
        e_3 = Numerical("e_3: ", operator.eq, 10.0, 5.0)
        e_4 = Numerical("e_4: ", operator.ne, 10.0, 5.0)
        r = and_(e_1, e_2, e_3) | e_4
        expected = ("(((e_1: 10.0 >= 10.0 True) & ((e_2: 10.0 < 20.0 True) & "
                    "(e_3: 10.0 == 5.0 False) False) False) | "
                    "(e_4: 10.0 != 5.0 True) True)")
        self.assertEqual(str(r), expected)

    def test_expression_debug(self):
        e_1 = Numerical("e_1", operator.ge, 10.0, 10.0)
        e_2 = Numerical("e_2", operator.lt, 10.0, 20.0)
        e_3 = Numerical("e_3", operator.eq, 10.0, 5.0)

        r = and_(e_1, e_2, e_3)
        self.assertEqual(r.debug(), e_3)

        e_1 = Numerical("e_1", operator.ge, 10.0, 10.0)
        e_2 = Numerical("e_2", operator.lt, 10.0, 5.0)
        e_3 = Numerical("e_3", operator.eq, 10.0, 5.0)

        r = and_(e_1, e_2, e_3)
        self.assertEqual(r.debug(), e_2)
