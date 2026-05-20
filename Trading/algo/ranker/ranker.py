from Trading.model.history import History, OHLC
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__file__)


class ScoreCalculator(BaseModel):
    """
    ScoreCalculator class is used to quantify a set of traits that is desirable
    in stocks, based on their historical data. It takes a history object and a window size
    and scores the stocks based on the historical data in the window.

    This class can be used in order to determine which stocks are
    the best to trade based on their historical data.

    The ScoreCalculator class is used in the PerfectRange class to rank
    stocks ranging behavior based on their historical data.
    """

    window: int

    @abstractmethod
    def calculate(self, history: History) -> float:
        pass


class RangeScorer(ScoreCalculator):
    """
    RangeScorer class is used to score stocks based on their historical data.
    It takes a history object and a window size and scores the stocks based on
    their historical data in the window.

    It finds the price level above which x % of the highs are and the price level
    below which x % of the lows are. It then calculates the ratio of these two price
    levels and returns the ratio as the score.
    """

    x_percent: float = 10.0

    def calculate(self, history: History):
        # Calculate the number of top elements needed
        length = len(history.high)
        top_count = int(length / self.x_percent)

        # Get the top lowest x% highs and top highest x% lows
        # top_highs = history.calculate_percentile(OHLC.HIGH, 100 - self.x_percent)
        # top_lows = history.calculate_percentile(OHLC.LOW, self.x_percent)

        # Calculate the diminished range height
        # ratio = top_highs / top_lows

        # minimize the standard deviation of highs and lows
        highs_std = history.calculate_std(OHLC.HIGH)
        highs_mean = history.calculate_mean(OHLC.HIGH)
        lows_std = history.calculate_std(OHLC.LOW)
        lows_mean = history.calculate_mean(OHLC.LOW)

        highs_std = highs_std / highs_mean
        lows_std = lows_std / lows_mean

        return 1 / (highs_std + lows_std)


class RangeCoherenceMetric(ScoreCalculator):
    """
    RangeCoherenceMetric class is used to calculate coherence metrics based on the
    historical data of the stock.
    It takes a history object and a window size and scores the stocks based on
    their historical data in the window.

    It finds the range coherence metric described in this paper.
    """

    x_percent: float = 10.0

    def calculate(self, history: History):
        p_high = history.calculate_percentile(OHLC.HIGH, 100 - self.x_percent)
        p_low = history.calculate_percentile(OHLC.LOW, self.x_percent)

        width = p_high - p_low
        if width <= 0:
            return 0.0

        clipped = [max(min(h, p_high) - max(l, p_low), 0)
                   for h, l in zip(history.high, history.low)]
        return sum(clipped) / (history.len * width)


class RobustRangeScorer(ScoreCalculator):
    """
    RobustRangeScorer identifies high-quality ranging environments by measuring:
    1. Outlier-resistant boundaries (using percentiles).
    2. Oscillation frequency (how much it bounces inside the range).
    3. Trend Penalty (penalizing diagonal movement).
    """

    upper_percentile: float = 90.0
    lower_percentile: float = 10.0

    def calculate(self, history: History) -> float:
        if history.len < 2:
            return 0.0

        # 1. Define boundaries robustly (Ignores massive single-candle wicks)
        resistance = history.calculate_percentile(OHLC.HIGH, self.upper_percentile)
        support = history.calculate_percentile(OHLC.LOW, self.lower_percentile)

        range_height = resistance - support
        if range_height <= 0:
            return 0.0  # Prevent division by zero
        if range_height / support < 0.2:
            return 0.0  # Range is too tight, likely not a good ranging environment

        # 2. Oscillation Ratio (Choppiness)
        # Sum of all intraday movement divided by the total range height.
        # A higher number means the stock is actively ping-ponging back and forth.
        total_movement = sum([h - l for h, l in zip(history.high, history.low)])
        oscillation_score = total_movement / range_height

        # 3. Trend Penalty (Flatness check)
        # Compare the average price of the first half of the window to the second half.
        # If they are very different, the "range" is drifting diagonally.
        midpoint = history.len // 2
        first_half_mean = sum(history.close[:midpoint]) / midpoint
        second_half_mean = sum(history.close[midpoint:]) / (history.len - midpoint)

        # Normalize the drift against the height of the range
        trend_drift = abs(first_half_mean - second_half_mean)
        flatness_penalty = trend_drift / range_height

        # 4. Final Score
        # Reward high oscillation, heavily penalize trend drift.
        # The +1 prevents division by zero and smooths the penalty.
        return oscillation_score / (1.0 + flatness_penalty)


class Ordering(BaseModel):
    """
    Ordering class is used to keep track of the ordering of stocks
    based on their historical data. It takes a list of stocks and
    orders them based on their historical data.
    """

    top_n: int
    score_calculator: RangeScorer | RangeCoherenceMetric | RobustRangeScorer
    is_bigger_better: bool = True
    scores: Optional[Dict[str, float]] = dict()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_history(self, history: History):
        score = self.score_calculator.calculate(history)
        score = round(score, 2)
        self.scores[history.symbol] = score

        if self.is_bigger_better:
            self.scores = dict(
                sorted(self.scores.items(), key=lambda item: item[1], reverse=True)[
                    : self.top_n
                ]
            )
        else:
            self.scores = dict(
                sorted(self.scores.items(), key=lambda item: item[1])[: self.top_n]
            )
