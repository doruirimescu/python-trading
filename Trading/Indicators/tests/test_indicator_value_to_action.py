import pytest
import unittest
from Trading.Indicators.indicator_value_to_action import IndicatorAction
from Trading.Indicators.indicator_value_to_action import IndicatorValueToAction

class TestIndicatorValueToAction(unittest.TestCase):

    def test_Overbought(self):
        iva = IndicatorValueToAction(70, 30, 5)
        self.assertEqual(iva.analyse(80), IndicatorAction.OVERBOUGHT)
        self.assertEqual(iva.analyse(100), IndicatorAction.OVERBOUGHT)
        self.assertEqual(iva.analyse(71), IndicatorAction.OVERBOUGHT)

    def test_Buy(self):
        iva = IndicatorValueToAction(70, 30, 5)
        self.assertEqual(iva.analyse(70), IndicatorAction.BUY)
        self.assertEqual(iva.analyse(56), IndicatorAction.BUY)
        self.assertEqual(iva.analyse(56), IndicatorAction.BUY)

    def test_Neutral(self):
        iva = IndicatorValueToAction(70, 30, 5)
        self.assertEqual(iva.analyse(55), IndicatorAction.NEUTRAL)
        self.assertEqual(iva.analyse(50), IndicatorAction.NEUTRAL)
        self.assertEqual(iva.analyse(45), IndicatorAction.NEUTRAL)

    def test_Sell(self):
        iva = IndicatorValueToAction(70, 30, 5)
        self.assertEqual(iva.analyse(31), IndicatorAction.SELL)
        self.assertEqual(iva.analyse(40), IndicatorAction.SELL)
        self.assertEqual(iva.analyse(44), IndicatorAction.SELL)

    def test_Oversold(self):
        iva = IndicatorValueToAction(70, 30, 5)
        self.assertEqual(iva.analyse(0), IndicatorAction.OVERSOLD)
        self.assertEqual(iva.analyse(29), IndicatorAction.OVERSOLD)
        self.assertEqual(iva.analyse(15), IndicatorAction.OVERSOLD)
