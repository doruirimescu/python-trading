from Trading.model.history import History
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict

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
    is_bigger_better: bool = False


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
    is_bigger_better: bool = False

    def calculate(self, history: History):
        # order the highs and lows of the last periods
        ordered_highs = sorted(history.high)
        ordered_lows = sorted(history.low)

        # get top lowest x% highs and top x% highest lows
        length = len(ordered_highs)
        top_highs = ordered_highs[int(length/self.x_percent)]
        top_lows = ordered_lows[-int(length/self.x_percent)]

        # this represents the diminished range height
        ratio = top_highs / top_lows

        # minimize the standard deviation of highs and lows
        from Trading.utils.calculations import calculate_standard_deviation, calculate_mean

        highs_std = calculate_standard_deviation(ordered_highs)
        highs_mean = calculate_mean(ordered_highs)
        lows_std = calculate_standard_deviation(ordered_lows)
        lows_mean = calculate_mean(ordered_lows)

        highs_std = highs_std / highs_mean
        lows_std = lows_std / lows_mean

        return ratio / (highs_std + lows_std)


class Ordering(BaseModel):
    '''
        Ordering class is used to keep track of the ordering of stocks
        based on their historical data. It takes a list of stocks and
        orders them based on their historical data.
    '''
    top_n: int
    score_calculator: RangeScorer
    scores: Optional[Dict[str, float]] = dict()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_history(self, history: History):
        score = self.score_calculator.calculate(history)
        score = round(score, 2)
        self.scores[history.symbol] = score

        is_bigger_better = self.score_calculator.is_bigger_better
        if is_bigger_better:
            self.scores = dict(sorted(self.scores.items(), key=lambda item: item[1],
                                      reverse=True)[:self.top_n])
        else:
            self.scores = dict(sorted(self.scores.items(), key=lambda item: item[1])[:self.top_n])
