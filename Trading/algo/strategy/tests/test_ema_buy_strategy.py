from Trading.algo.strategy.strategy import EmaBuyStrategy, Action, StrategyType
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
import unittest
from unittest.mock import MagicMock
import pandas as pd


class TestEmaBuyStrategy(unittest.TestCase):
    def test_side_trend_no_action(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0]
        mid_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.SIDE]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 0.1)

        self.assertEqual(Action.NO, response)

        fast_indicator.calculate_ema.assert_called_once()
        mid_indicator.calculate_ema.assert_called_once()
        slow_indicator.calculate_ema.assert_called_once()
        slow_indicator.get_trend.assert_called_once()

    def test_up_trend_no_action(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0]
        mid_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.UP]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 0.9)

        self.assertEqual(Action.NO, response)

        fast_indicator.calculate_ema.assert_called_once()
        mid_indicator.calculate_ema.assert_called_once()
        slow_indicator.calculate_ema.assert_called_once()
        slow_indicator.get_trend.assert_called_once()

    def test_up_trend_buy_action_close_take_profit(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [3.0, 3.0, 3.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [1.0, 1.0, 1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.UP, TrendAnalysis.UP, TrendAnalysis.UP]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 2.2)

        self.assertEqual(Action.BUY, response)

        response = strategy.analyse(pd.DataFrame(), 2.2)
        self.assertEqual(Action.NO, response)

        response = strategy.analyse(pd.DataFrame(), 2.45)
        self.assertEqual(Action.STOP, response)

    def test_up_trend_buy_action_close_stop_loss(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [3.0, 3.0, 3.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [1.0, 1.0, 1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.UP, TrendAnalysis.UP, TrendAnalysis.UP]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 2.2)

        self.assertEqual(Action.BUY, response)

        response = strategy.analyse(pd.DataFrame(), 2.2)
        self.assertEqual(Action.NO, response)

        response = strategy.analyse(pd.DataFrame(), 1.0)
        self.assertEqual(Action.STOP, response)

    def test_up_trend_buy_action_then_trend_changes_side(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [3.0, 3.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [1.0, 1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.UP, TrendAnalysis.SIDE]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 2.2)

        self.assertEqual(Action.BUY, response)

        response = strategy.analyse(pd.DataFrame(), 2.2)
        self.assertEqual(Action.STOP, response)

    def test_up_trend_buy_action_then_trend_changes_down(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [3.0, 3.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [1.0, 1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.UP, TrendAnalysis.DOWN]

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 2.2)

        self.assertEqual(Action.BUY, response)

        response = strategy.analyse(pd.DataFrame(), 2.2)
        self.assertEqual(Action.STOP, response)

    def test_get_type(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        strategy = EmaBuyStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)

        self.assertEqual(StrategyType.BUY.value, strategy.get_type())
