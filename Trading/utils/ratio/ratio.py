from typing import List
from itertools import combinations
from abc import abstractmethod

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

    def __repr__(self):
        return f"Ratio({self.numerator}, {self.denominator})"

class RatioGenerator:
    def __init__(self, symbols: List[str], choose_k: int = 2) -> None:
        self.symbols = symbols
        self.choose_k = choose_k
        self.numerator_index = 0
        self.denominator_index = 0
        self.current_k = 0


    @abstractmethod
    def _process(self, ratio: Ratio, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        for n_combinations in range(self.choose_k, int(len(self.symbols)/2)):
            cmb = list(combinations(self.symbols, n_combinations))
            for self.numerator_index, numerator in enumerate(cmb):
                for self.denominator_index in range(self.numerator_index + 1, len(cmb)):
                    denominator = cmb[self.denominator_index]

                    ratio = Ratio(list(numerator), list(denominator))
                    self._process(ratio=ratio,
                                  iteration_info=(f"k: {self.choose_k} numerator index:"
                                                  f"{self.numerator_index} denominator index:"
                                                  f"{self.denominator_index}"), *args, **kwargs)
