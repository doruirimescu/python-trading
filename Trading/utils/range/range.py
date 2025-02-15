from typing import List, Dict, Optional
from Trading.model.history import History
from Trading.utils.custom_logging import get_logger

MAIN_LOGGER = get_logger("range.py")



def calculate_rank(history: History, periods: int):
    # calculate how close to a perfect range the last periods are
    # 0 means perfect range, 1 means no range
    max_of_last_periods = max(history.high[-periods:])
    min_of_last_periods = min(history.low[-periods:])

    range_size = max_of_last_periods - min_of_last_periods

    sum_of_ranges = 0
    for h, l in zip(history.high[-periods:], history.low[-periods:]):
        sum_of_ranges += abs(h - l)
    return (range_size*periods - sum_of_ranges) / range_size

def calculate_rank_2(history: History, periods: int):
    # order the highs and lows of the last periods
    ordered_highs = sorted(history.high[-periods:])
    ordered_lows = sorted(history.low[-periods:])

    # get top lowest 10% highs and top highest 10% lows
    top_highs = ordered_highs[int(periods/10)]
    top_lows = ordered_lows[-int(periods/10)]

    rank = -top_highs / top_lows
    return rank

class PerfectRange:
    def __init__(self, periods: int, top_n: int = 1, tolerance: Optional[float] = None):
        self.periods = periods
        self.ranks: Dict[str, float] = dict()
        self.top_n = top_n
        self.tolerance = tolerance

    def add_history(self, history: History, current_price: Optional[float], range_height: Optional[float] = None):
        # if current price is greater or smaller than the last periods high or low, respectively,
        # then the range is not perfect
        max_h = max(history.high[-self.periods:])
        min_l = min(history.low[-self.periods:])
        if current_price:
            if current_price > max_h:
                return
            if current_price < min_l:
                return
        if self.tolerance:
            if current_price > min_l * (1+self.tolerance):
                return
        if range_height and max_h / min_l < range_height:
            return
        rank = calculate_rank_2(history, self.periods)
        rank = round(rank, 2)
        self.ranks[history.symbol] = rank
        self.ranks = dict(sorted(self.ranks.items(), key=lambda item: item[1])[:self.top_n])
        MAIN_LOGGER.info(f"Top {self.top_n} ranks: {self.ranks}")
        MAIN_LOGGER.info(f"Current price: {current_price} Max high: {max_h} Min low: {min_l}")
