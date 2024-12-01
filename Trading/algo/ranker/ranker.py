from Trading.model.history import History, OHLC
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__file__)
class ScoreCalculator(BaseModel):
    '''
        ScoreCalculator class is used to quantify a set of traits that is desirable
        in stocks, based on their historical data. It takes a history object and a window size
        and scores the stocks based on the historical data in the window.

        This class can be used in order to determine which stocks are
        the best to trade based on their historical data.

        The ScoreCalculator class is used in the PerfectRange class to rank
        stocks ranging behavior based on their historical data.
    '''
    window: int

    @abstractmethod
    def calculate(self, history: History) -> float:
        pass


class RangeScorer(ScoreCalculator):
    '''
        RangeScorer class is used to score stocks based on their historical data.
        It takes a history object and a window size and scores the stocks based on
        their historical data in the window.

        It finds the price level above which x % of the highs are and the price level
        below which x % of the lows are. It then calculates the ratio of these two price
        levels and returns the ratio as the score.
    '''
    x_percent: float = 10.0

    def calculate(self, history: History):
        # Calculate the number of top elements needed
        length = len(history.high)
        top_count = int(length / self.x_percent)

        # Get the top lowest x% highs and top highest x% lows
        #top_highs = history.calculate_percentile(OHLC.HIGH, 100 - self.x_percent)
        #top_lows = history.calculate_percentile(OHLC.LOW, self.x_percent)

        # Calculate the diminished range height
        #ratio = top_highs / top_lows

        # minimize the standard deviation of highs and lows
        highs_std = history.calculate_std(OHLC.HIGH)
        highs_mean = history.calculate_mean(OHLC.HIGH)
        lows_std = history.calculate_std(OHLC.LOW)
        lows_mean = history.calculate_mean(OHLC.LOW)

        highs_std = highs_std / highs_mean
        lows_std = lows_std / lows_mean

        return 1 / (highs_std + lows_std)


class RangeCoherenceMetric(ScoreCalculator):
    '''
        RangeCoherenceMetric class is used to calculate coherence metrics based on the
        historical data of the stock.
        It takes a history object and a window size and scores the stocks based on
        their historical data in the window.

        It finds the range coherence metric described in this paper.
    '''

    def calculate(self, history: History):
        p_high = history.get_highest(OHLC.HIGH)
        p_low = history.get_lowest(OHLC.LOW)

        # Calculate the diminished range width
        width = p_high - p_low

        # sum over high - low for each candle
        s = sum([h - l for h, l in zip(history.high, history.low)]) / width

        n = history.len
        return s / n

class Ordering(BaseModel):
    '''
        Ordering class is used to keep track of the ordering of stocks
        based on their historical data. It takes a list of stocks and
        orders them based on their historical data.
    '''
    top_n: int
    score_calculator: RangeScorer | RangeCoherenceMetric
    is_bigger_better: bool = True
    scores: Optional[Dict[str, float]] = dict()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_history(self, history: History):
        score = self.score_calculator.calculate(history)
        score = round(score, 2)
        self.scores[history.symbol] = score

        if self.is_bigger_better:
            self.scores = dict(sorted(self.scores.items(), key=lambda item: item[1],
                                      reverse=True)[:self.top_n])
        else:
            self.scores = dict(sorted(self.scores.items(), key=lambda item: item[1])[:self.top_n])
