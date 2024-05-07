from typing import List, Optional
from itertools import combinations
from abc import abstractmethod
from Trading.utils.custom_logging import get_logger
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

    def __repr__(self):
        return f"Ratio({self.numerator}, {self.denominator})"

class RatioPermutationIndices:
    def __init__(self, k: int, numerator_index: int, denominator_index: int) -> None:
        self.k = k
        self.numerator_index = numerator_index
        self.denominator_index = denominator_index

    def __repr__(self):
        return f"RatioPermutationIndices(k: {self.k}, numerator_index: {self.numerator_index}, denominator_index: {self.denominator_index})"
class RatioGenerator:
    def __init__(self, symbols: List[str], choose_k: int = 2) -> None:
        self.symbols = symbols
        self.choose_k = choose_k
        self.numerator_index = 0
        self.denominator_index = 0
        self.current_k = 0
        self.candidates = []

    @abstractmethod
    def _process(self, ratio: Ratio, *args, **kwargs):
        pass

    def get_permutations(self, perms: List[RatioPermutationIndices]):
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
                result = self._process(ratio=ratio,
                              iteration_info=(f"k: {self.choose_k} numerator index:"
                                              f"{self.numerator_index} denominator index:"
                                              f"{self.denominator_index}"), *args, **kwargs)
                if result:
                    self.candidates.append((self.choose_k, self.numerator_index, self.denominator_index))
                cnt += 1
                if cnt % 100 == 0:
                    MAIN_LOGGER.info(f"Processed {cnt} ratios")
        MAIN_LOGGER.info(f"Processed {cnt} ratios")
        MAIN_LOGGER.info(f"Found {len(self.candidates)} candidates")
        print(self.candidates)
