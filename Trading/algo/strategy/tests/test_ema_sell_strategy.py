from Trading.algo.strategy.strategy import EmaSellStrategy, Action
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
import unittest
from unittest.mock import MagicMock
import pandas as pd


class TestEmaSellStrategy(unittest.TestCase):
    def test_side_trend_no_action(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0]
        mid_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.SIDE]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 0.1)

        self.assertEqual(Action.NO, response)

        fast_indicator.calculate_ema.assert_called_once()
        mid_indicator.calculate_ema.assert_called_once()
        slow_indicator.calculate_ema.assert_called_once()
        slow_indicator.get_trend.assert_called_once()

    def test_down_trend_no_action(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0]
        mid_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.calculate_ema.side_effect = [1.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.DOWN]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 0.9)

        self.assertEqual(Action.NO, response)

        fast_indicator.calculate_ema.assert_called_once()
        mid_indicator.calculate_ema.assert_called_once()
        slow_indicator.calculate_ema.assert_called_once()
        slow_indicator.get_trend.assert_called_once()

    def test_up_trend_sell_action_close_take_profit(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0, 1.0, 1.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [3.0, 3.0, 3.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.DOWN, TrendAnalysis.DOWN, TrendAnalysis.DOWN]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 1.5)

        self.assertEqual(Action.SELL, response)

        response = strategy.analyse(pd.DataFrame(), 1.5)
        self.assertEqual(Action.NO, response)

        response = strategy.analyse(pd.DataFrame(), 1.34)
        self.assertEqual(Action.STOP, response)

    def test_down_trend_sell_action_close_stop_loss(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0, 1.0, 1.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [3.0, 3.0, 3.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.DOWN, TrendAnalysis.DOWN, TrendAnalysis.DOWN]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 1.5)

        self.assertEqual(Action.SELL, response)

        response = strategy.analyse(pd.DataFrame(), 1.5)
        self.assertEqual(Action.NO, response)

        response = strategy.analyse(pd.DataFrame(), 3.0)
        self.assertEqual(Action.STOP, response)

    def test_down_trend_sell_action_then_trend_changes_side(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0, 1.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [3.0, 3.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.DOWN, TrendAnalysis.SIDE]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 1.5)

        self.assertEqual(Action.SELL, response)

        response = strategy.analyse(pd.DataFrame(), 1.5)
        self.assertEqual(Action.STOP, response)

    def test_down_trend_sell_action_then_trend_changes_up(self):
        fast_indicator = MagicMock()
        mid_indicator = MagicMock()
        slow_indicator = MagicMock()

        fast_indicator.calculate_ema.side_effect = [1.0, 1.0]
        mid_indicator.calculate_ema.side_effect = [2.0, 2.0]
        slow_indicator.calculate_ema.side_effect = [3.0, 3.0]
        slow_indicator.get_trend.side_effect = [TrendAnalysis.DOWN, TrendAnalysis.UP]

        strategy = EmaSellStrategy(0.1, fast_indicator, mid_indicator, slow_indicator)
        response = strategy.analyse(pd.DataFrame(), 1.5)

        self.assertEqual(Action.SELL, response)

        response = strategy.analyse(pd.DataFrame(), 1.5)
        self.assertEqual(Action.STOP, response)
