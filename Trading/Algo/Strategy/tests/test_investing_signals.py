import pytest
import unittest
from unittest.mock import MagicMock
from Trading.Algo.Strategy.strategy import *
from Trading.Algo.TechnicalAnalyzer.technical_analysis import TechnicalAnalysis

class TestInvestingSignals(unittest.TestCase):
#! Test Neutral
    def test_NEUTRAL_STRONG_SELL_SELL(self):
        #Act
        action = decideAction(TechnicalAnalysis.NEUTRAL, TechnicalAnalysis.STRONG_SELL)

        #Assert
        self.assertEqual(Action.SELL, action)

    def test_NEUTRAL_SELL_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.NEUTRAL, TechnicalAnalysis.SELL)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_NEUTRAL_NEUTRAL_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.NEUTRAL, TechnicalAnalysis.NEUTRAL)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_NEUTRAL_BUY_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.NEUTRAL, TechnicalAnalysis.BUY)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_NEUTRAL_STRONG_BUY(self):
        #Act
        action = decideAction(TechnicalAnalysis.NEUTRAL, TechnicalAnalysis.STRONG_BUY)

        #Assert
        self.assertEqual(Action.BUY, action)

#! Test Strong Sell
    def test_STRONG_SELL_STRONG_SELL_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_SELL, TechnicalAnalysis.STRONG_SELL)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_STRONG_SELL_SELL_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_SELL, TechnicalAnalysis.SELL)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_STRONG_SELL_NEUTRAL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_SELL, TechnicalAnalysis.NEUTRAL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_STRONG_SELL_BUY_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_SELL, TechnicalAnalysis.BUY)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_STRONG_SELL_STRONG_BUY_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_SELL, TechnicalAnalysis.STRONG_BUY)

        #Assert
        self.assertEqual(Action.STOP, action)

#! Test Sell
    def test_SELL_STRONG_SELL_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.SELL, TechnicalAnalysis.STRONG_SELL)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_SELL_NEUTRAL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.SELL, TechnicalAnalysis.NEUTRAL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_SELL_BUY_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.SELL, TechnicalAnalysis.BUY)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_SELL_STRONG_BUY_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.SELL, TechnicalAnalysis.STRONG_BUY)

        #Assert
        self.assertEqual(Action.STOP, action)

#! Test BUY
    def test_BUY_STRONG_SELL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.BUY, TechnicalAnalysis.STRONG_SELL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_BUY_SELL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.BUY, TechnicalAnalysis.SELL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_BUY_NEUTRAL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.BUY, TechnicalAnalysis.NEUTRAL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_BUY_BUY_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.BUY, TechnicalAnalysis.BUY)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_BUY_STRONG_BUY_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.BUY, TechnicalAnalysis.STRONG_BUY)

        #Assert
        self.assertEqual(Action.NO, action)

#! Test STRONG BUY
    def test_STRONG_BUY_STRONG_SELL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_BUY, TechnicalAnalysis.STRONG_SELL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_STRONG_BUY_SELL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_BUY, TechnicalAnalysis.SELL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_STRONG_BUY_NEUTRAL_STOP(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_BUY, TechnicalAnalysis.NEUTRAL)

        #Assert
        self.assertEqual(Action.STOP, action)

    def test_STRONG_BUY_BUY_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_BUY, TechnicalAnalysis.BUY)

        #Assert
        self.assertEqual(Action.NO, action)

    def test_STRONG_BUY_STRONG_BUY_NO(self):
        #Act
        action = decideAction(TechnicalAnalysis.STRONG_BUY, TechnicalAnalysis.STRONG_BUY)

        #Assert
        self.assertEqual(Action.NO, action)
if __name__ == '__main__':
    unittest.main()