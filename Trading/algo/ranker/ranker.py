from Trading.model.history import History
from abc import ABC, abstractmethod
from typing import Dict, List

class ScoreCalculator(ABC):
    '''
        ScoreCalculator class is used to quantify a set of traits that is desirable
        in stocks, based on their historical data. It takes a history object and a window size
        and scores the stocks based on the historical data in the window.

        This class can be used in order to determine which stocks are
        the best to trade based on their historical data.

        The ScoreCalculator class is used in the PerfectRange class to rank
        stocks ranging behavior based on their historical data.
    '''
    def __init__(self, window: int, is_bigger_better=False) -> None:
        self._window = window
        self._is_bigger_better = is_bigger_better

    @abstractmethod
    def calculate(self, history: History) -> float:
        pass

class Ordering:
    '''
        Ordering class is used to keep track of the ordering of stocks
        based on their historical data. It takes a list of stocks and
        orders them based on their historical data.
    '''
    def __init__(self, top_n: int, score_calculator: ScoreCalculator) -> None:
        self._top_n = top_n
        self._scores: Dict[str, float] = dict()
        self._score_calculator = score_calculator

    def add_history(self, history: History):
        score = self._score_calculator.calculate(history)
        score = round(score, 2)
        self._scores[history.symbol] = score

        is_bigger_better = self._score_calculator._is_bigger_better
        if is_bigger_better:
            self._scores = dict(sorted(self._scores.items(), key=lambda item: item[1],
                                      reverse=True)[:self._top_n])
        else:
            self._scores = dict(sorted(self._scores.items(), key=lambda item: item[1])[:self._top_n])

    def scores(self):
        return self._scores

class RangeScorer(ScoreCalculator):
    '''
        RangeScorer class is used to score stocks based on their historical data.
        It takes a history object and a window size and scores the stocks based on
        their historical data in the window.

        It finds the price level above which x % of the highs are and the price level
        below which x % of the lows are. It then calculates the ratio of these two price
        levels and returns the ratio as the score.
    '''
    def __init__(self, window: int, x_percent: float = 10) -> None:
        super().__init__(window, is_bigger_better=True)
        self._x_percent = x_percent

    def calculate(self, history: History):
        # order the highs and lows of the last periods
        ordered_highs = sorted(history.high)
        ordered_lows = sorted(history.low)

        # get top lowest x% highs and top x% highest lows
        length = len(ordered_highs)
        top_highs = ordered_highs[int(length/self._x_percent)]
        top_lows = ordered_lows[-int(length/self._x_percent)]

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
