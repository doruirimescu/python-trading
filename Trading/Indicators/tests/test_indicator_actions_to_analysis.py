import pytest
import unittest
from Trading.Indicators.indicator_value_to_action import IndicatorAction
from Trading.Indicators.indicator_actions_to_analysis import IndicatorActionsToAnalysis
from Trading.InvestingAPI.investing_technical import TechnicalAnalysis
class TestIndicatorActionsToAnalysis(unittest.TestCase):

    #Take these from Investing.com
    def test_B9_S0_N1(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.STRONG_BUY, result)

    def test_B7_S1_N2(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.STRONG_BUY, result)

    def test_B3_S2_N5(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.BUY, result)

    def test_B0_S6_N4(self):
        actions = [IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.STRONG_SELL, result)

    def test_B3_S3_N5(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.NEUTRAL, result)

    def test_B1_S8_N5(self):
        actions = [IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.STRONG_SELL, result)

    def test_B4_S4_N3(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.NEUTRAL, result)

    #Other tests
    def test_B2_S1_N5(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TechnicalAnalysis.BUY, result)
