import pytest
import unittest
from Trading.Indicators.indicator_value_to_action import IndicatorAction
from Trading.Indicators.indicator_actions_to_analysis import IndicatorActionsToAnalysis
from Trading.InvestingAPI.investing_technical import TechnicalAnalysis as TA
class TestIndicatorActionsToAnalysis(unittest.TestCase):
    def BSN(self, buy, sell, neutral):
        actions = list()
        for i in range(buy):
            actions.append(IndicatorAction.BUY)
        for i in range(sell):
            actions.append(IndicatorAction.SELL)
        for i in range(neutral):
            actions.append(IndicatorAction.NEUTRAL)
        return IndicatorActionsToAnalysis().convert(actions)

    #Take these from Investing.com
    def test_1(self):
        result = self.BSN(9,0,1)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_2(self):
        result = self.BSN(7,1,2)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_3(self):
        result = self.BSN(3,2,5)
        self.assertEqual(TA.BUY, result)

    def test_4(self):
        result = self.BSN(0,6,4)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_5(self):
        result = self.BSN(3,3,5)
        self.assertEqual(TA.NEUTRAL, result)

    def test_6(self):
        result = self.BSN(1,8,5)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_7(self):
        result = self.BSN(4,4,3)
        self.assertEqual(TA.NEUTRAL, result)

    def test_8(self):
        result = self.BSN(8,0,3)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_9(self):
        result = self.BSN(3,4,3)
        self.assertEqual(TA.SELL, result)

    def test_10(self):
        result = self.BSN(3,4,4)
        self.assertEqual(TA.SELL, result)

    def test_11(self):
        result = self.BSN(2,6,3)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_12(self):
        result = self.BSN(5,0,6)
        self.assertEqual(TA.BUY, result)

    def test_13(self):
        result = self.BSN(5,1,5)
        self.assertEqual(TA.BUY, result)

    def test_14(self):
        result = self.BSN(3,4,3)
        self.assertEqual(TA.SELL, result)

    def test_15(self):
        result = self.BSN(3,3,3)
        self.assertEqual(TA.NEUTRAL, result)

    def test_16(self):
        result = self.BSN(0,6,4)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_17(self):
        result = self.BSN(1,8,1)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_18(self):
        result = self.BSN(2,6,2)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_19(self):
        result = self.BSN(5,2,3)
        self.assertEqual(TA.BUY, result)

    def test_20(self):
        result = self.BSN(1,6,4)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_21(self):
        result = self.BSN(4,5,2)
        self.assertEqual(TA.SELL, result)

    def test_22(self):
        result = self.BSN(4,1,4)
        self.assertEqual(TA.BUY, result)

    def test_23(self):
        result = self.BSN(4,2,4)
        self.assertEqual(TA.BUY, result)

    def test_24(self):
        result = self.BSN(7,0,3)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_25(self):
        result = self.BSN(7,3,1)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_28(self):
        result = self.BSN(1,5,2)
        self.assertEqual(TA.SELL, result)

    def test_26(self):
        result = self.BSN(4,3,4)
        self.assertEqual(TA.BUY, result)

    def test_27(self):
        result = self.BSN(8,1,1)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_28(self):
        result = self.BSN(1,9,1)
        self.assertEqual(TA.STRONG_SELL, result)

    def test_29(self):
        result = self.BSN(6,3,1)
        self.assertEqual(TA.STRONG_BUY, result)

    def test_30(self):
        result = self.BSN(5,3,2)
        self.assertEqual(TA.BUY, result)

    def test_31(self):
        result = self.BSN(4,2,2)
        self.assertEqual(TA.BUY, result)

    def test_32(self):
        result = self.BSN(2,4,5)
        self.assertEqual(TA.SELL, result)

    def test_33(self):
        result = self.BSN(8,2,1)
        self.assertEqual(TA.STRONG_BUY, result)

    #Other tests
    def test_B2_S1_N5(self):
        actions = [IndicatorAction.BUY, IndicatorAction.BUY, IndicatorAction.SELL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL, IndicatorAction.NEUTRAL]
        result = IndicatorActionsToAnalysis().convert(actions)
        self.assertEqual(TA.BUY, result)
