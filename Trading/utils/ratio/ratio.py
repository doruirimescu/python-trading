from typing import List, Optional, Dict
from itertools import combinations
from abc import abstractmethod
from Trading.utils.custom_logging import get_logger
from Trading.utils.history import History
from datetime import datetime

MAIN_LOGGER = get_logger("ratio.py")


class Ratio:
    def __init__(self, numerator: List[str], denominator: List[str]) -> None:
        # assert instance
        assert isinstance(numerator, list)
        assert isinstance(denominator, list)
        # assert length
        assert len(numerator) > 0
        assert len(denominator) > 0

        self.numerator = numerator
        self.denominator = denominator
        self.mean = None
        self.std = None

        self.histories:Dict[str, History] = dict()
        self.dates = []

    def __repr__(self):
        return f"Ratio({self.numerator}, {self.denominator})"

    def _check_all_dates(self):
        dates_len = len(self.histories[self.numerator[0]]["date"])
        dates = self.histories[self.numerator[0]]["date"]
        for symbol in self.numerator:
            if len(self.histories[symbol]["date"]) != dates_len:
                raise ValueError("Dates are not the same length")
            if self.histories[symbol]["date"] != dates:
                raise ValueError("Dates are not the same")
        for symbol in self.denominator:
            if len(self.histories[symbol]["date"]) != dates_len:
                raise ValueError("Dates are not the same length")
            if self.histories[symbol]["date"] != dates:
                raise ValueError("Dates are not the same")
        return True

    def add_history(self, symbol: str, history):
        self.histories[symbol] = history

    def eliminate_nonintersecting_dates(self):
        # for each symbol, remove dates and values that are not in all symbols
        dates = set(self.histories[self.numerator[0]]["date"])
        for symbol in self.numerator + self.denominator:
            dates = dates.intersection(set(self.histories[symbol]["date"]))

        dates_to_remove = []
        for symbol in self.numerator + self.denominator:
            for d in self.histories[symbol]["date"]:
                if d not in dates:
                    dates_to_remove.append(d)
        for symbol in self.numerator + self.denominator:
            for d in dates_to_remove:
                try:
                    i = self.histories[symbol]["date"].index(d)
                    self.histories[symbol]["date"].pop(i)
                    self.histories[symbol]["close"].pop(i)
                except ValueError:
                    pass
            self._normalize_prices(symbol)
        self.dates = self.histories[self.numerator[0]]["date"]
        self._check_all_dates()


    def _normalize_prices(self, symbol):
        history = self.histories[symbol]
        self.histories[symbol]["normalized"] = [
            x / history["close"][0] for x in history["close"]
        ]

    def _get_price_at_date(self, date: str, symbol: str):
        history = self.histories[symbol]
        for i, d in enumerate(history["date"]):
            if str(d) == str(date):
                return history["close"][i]
        return None

    def _get_prices_at_date(self, symbols: List[str], date: str):
        prices = []
        for symbol in symbols:
            prices.append(self._get_price_at_date(date, symbol))
        return prices

    def get_numerator_prices_at_date(self, date: str):
        return self._get_prices_at_date(self.numerator, date)

    def get_denominator_prices_at_date(self, date: str):
        return self._get_prices_at_date(self.denominator, date)

    def get_numerator_histories(self):
        return [self.histories[symbol] for symbol in self.numerator]

    def get_denominator_histories(self):
        return [self.histories[symbol] for symbol in self.denominator]

    def calculate_ratio(self):
        numerator_histories = self.get_numerator_histories()
        denominator_histories = self.get_denominator_histories()

        if len(numerator_histories) != len(denominator_histories):
            raise ValueError("Histories are not the same length")

        N_DAYS = len(numerator_histories[0]["date"])
        numerator_total = [0] * N_DAYS
        for symbol in self.numerator:
            normalized_prices = self.histories[symbol]["normalized"]
            numerator_total = [
                x + y for x, y in zip(numerator_total, normalized_prices)
            ]

        denominator_total = [0] * N_DAYS
        for symbol in self.denominator:
            normalized_prices = self.histories[symbol]["normalized"]
            denominator_total = [
                x + y for x, y in zip(denominator_total, normalized_prices)
            ]

        ratio_values = []
        for i in range(N_DAYS):
            ratio_values.append(numerator_total[i] / denominator_total[i])
        self.ratio_values = ratio_values
        from Trading.utils.calculations import calculate_mean, calculate_standard_deviation
        self.mean = calculate_mean(ratio_values)
        self.std = calculate_standard_deviation(ratio_values)
        return ratio_values

    def get_next_date_at_mean(self, date: str, tolerance: float = 0.01) -> Optional[datetime]:
        i = self.dates.index(str(date))
        for j in range(i, len(self.dates)):
            if abs(self.ratio_values[j] - self.mean) < tolerance:
                return datetime.fromisoformat(self.dates[j])
        return None

    def get_ratio_value_at_date(self, date: str):
        i = self.dates.index(date)
        return self.ratio_values[i]

class RatioPermutationIndices:
    def __init__(self, k: int, numerator_index: int, denominator_index: int) -> None:
        self.k = k
        self.numerator_index = numerator_index
        self.denominator_index = denominator_index

    def __repr__(self):
        return f"RatioPermutationIndices(k: {self.k}, numerator_index: {self.numerator_index}, denominator_index: {self.denominator_index})"


class RatioGenerator:
    def __init__(self, symbols: List[str], choose_k: Optional[int] = None) -> None:
        self.symbols = symbols
        self.choose_k = choose_k
        self.numerator_index = 0
        self.denominator_index = 0
        self.current_k = 0
        self.candidates = []

    @abstractmethod
    def _process(self, ratio: Ratio, *args, **kwargs):
        pass

    def get_permutations(self, perms: List[RatioPermutationIndices]) -> List[Ratio]:
        ratios = []
        for p in perms:
            cmb = list(combinations(self.symbols, p.k))
            numerator = cmb[p.numerator_index]
            denominator = cmb[p.denominator_index]
            ratio = Ratio(list(numerator), list(denominator))
            ratios.append(ratio)
        return ratios

    def run(self, *args, **kwargs):
        cmb = list(combinations(self.symbols, self.choose_k))
        cnt = 0
        for self.numerator_index, numerator in enumerate(cmb):
            for self.denominator_index in range(self.numerator_index + 1, len(cmb)):
                denominator = cmb[self.denominator_index]
                ratio = Ratio(list(numerator), list(denominator))
                result = self._process(
                    ratio=ratio,
                    iteration_info=(
                        f"k: {self.choose_k} numerator index:"
                        f"{self.numerator_index} denominator index:"
                        f"{self.denominator_index}"
                    ),
                    *args,
                    **kwargs,
                )
                if result:
                    self.candidates.append(
                        (self.choose_k, self.numerator_index, self.denominator_index)
                    )
                cnt += 1
                if cnt % 100 == 0:
                    MAIN_LOGGER.info(f"Processed {cnt} ratios")
        MAIN_LOGGER.info(f"Processed {cnt} ratios")
        MAIN_LOGGER.info(f"Found {len(self.candidates)} candidates")
        print(self.candidates)
