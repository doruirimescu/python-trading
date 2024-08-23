from typing import List, Optional, Dict
from abc import abstractmethod
from Trading.utils.custom_logging import get_logger
from Trading.model.history import History, OHLC
from datetime import datetime
from Trading.utils.ratio.combinatorics import get_all_ratios

MAIN_LOGGER = get_logger("ratio.py")


class DateNotFoundError(Exception):
    pass


from enum import Enum


class CurrentHolding(Enum):
    NUMERATOR = "numerator"
    DENOMINATOR = "denominator"
    NONE = "none"


class Ratio:
    def __init__(
        self, numerator: List[str], denominator: List[str], ohlc: OHLC = OHLC.CLOSE
    ) -> None:
        if not isinstance(numerator, list):
            raise ValueError("Numerator must be a list")
        if not isinstance(denominator, list):
            raise ValueError("Denominator must be a list")
        if len(numerator) == 0 or len(denominator) == 0:
            raise ValueError("Numerator or denominator cannot be empty")
        if len(numerator) != len(denominator):
            raise ValueError("Numerator and denominator must have the same length")
        self.numerator = numerator
        self.denominator = denominator
        self.mean = None
        self.std = None
        self.ohlc = ohlc.value

        self.histories: Dict[str, History] = dict()
        self.normalized_histories: Dict[str, History] = dict()
        self.dates: List[str] = []

    def __repr__(self):
        return f"Ratio({self.numerator}, {self.denominator})"

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
                    self.histories[symbol][self.ohlc].pop(i)
                except ValueError:
                    pass
            self._normalize_prices(symbol)
        self.dates = self.histories[self.numerator[0]]["date"]
        self._check_all_dates()

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

        n_dates = len(numerator_histories[0]["date"])
        numerator_total = [0] * n_dates
        for symbol in self.numerator:
            normalized_prices = self.normalized_histories[symbol]
            numerator_total = [
                x + y for x, y in zip(numerator_total, normalized_prices)
            ]

        denominator_total = [0] * n_dates
        for symbol in self.denominator:
            normalized_prices = self.normalized_histories[symbol]
            denominator_total = [
                x + y for x, y in zip(denominator_total, normalized_prices)
            ]

        ratio_values = []
        for i in range(n_dates):
            ratio_values.append(numerator_total[i] / denominator_total[i])
        self.ratio_values = ratio_values
        from Trading.utils.calculations import (
            calculate_mean,
            calculate_standard_deviation,
        )

        self.mean = calculate_mean(ratio_values)
        self.std = calculate_standard_deviation(ratio_values)
        return ratio_values

    def get_next_date_at_mean(
        self, date: datetime, tolerance: float = 0.001
    ) -> Optional[datetime]:
        i = self.dates.index(date)
        for j in range(i + 1, len(self.dates)):
            if abs(self.ratio_values[j] - self.mean) < tolerance:
                return self.dates[j], j
        raise DateNotFoundError("No date found")

    def get_ratio_value_at_date(self, date: datetime):
        i = self.dates.index(date)
        return self.ratio_values[i]

    def _normalize_prices(self, symbol):
        history = self.histories[symbol]
        self.normalized_histories[symbol] = [
            x / history[self.ohlc][0] for x in history[self.ohlc]
        ]

    def _get_price_at_date(self, date: datetime, symbol: str):
        history = self.histories[symbol]
        for i, d in enumerate(history["date"]):
            if d == date:
                return history[self.ohlc][i]
        return None

    def _get_prices_at_date(self, symbols: List[str], date: datetime):
        prices = []
        for symbol in symbols:
            prices.append(self._get_price_at_date(date, symbol))
        return prices

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

    def run(self, *args, **kwargs):
        all_ratios = get_all_ratios(self.symbols, self.choose_k)

        for i, ratio in enumerate(all_ratios):
            n, d = ratio
            ratio = Ratio(list(n), list(d))
            result = self._process(
                ratio=ratio,
                iteration_info=(f"k: {self.choose_k} index: {i}"),
                *args,
                **kwargs,
            )
            if result:
                self.candidates.append((self.choose_k))
            if (i + 1) % 100 == 0:
                MAIN_LOGGER.info(f"Processed {i+1} ratios")
        MAIN_LOGGER.info(f"Processed {i+1} ratios")
        MAIN_LOGGER.info(f"Found {len(self.candidates)} candidates")
        print(self.candidates)
