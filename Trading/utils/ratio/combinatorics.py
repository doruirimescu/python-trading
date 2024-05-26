from itertools import combinations, islice
import math
from typing import List

def get_all_ratios(symbols: List, k: int) -> List:
    """Get all possible ratios of k symbols from the list of symbols. k is the
    number of symbols in the numerator and denominator

    Returns:
        List: List of all possible ratios of n symbols
    """
    all_ratios = list(combinations((combinations(symbols, k)), 2))
    return all_ratios

def get_ith_ratio(symbols:List, k: int, i: int) -> List:
    """Get the ith ratio of k symbols from the list of symbols. k is the
    number of symbols in the numerator and denominator

    Returns:
        List: List of all possible ratios of n symbols
    """
    ratios = get_all_ratios(symbols, k)
    return next(islice(ratios, i, None))

def n_choose_k(n: int, k: int) -> int:
    """Calculate n choose k

    Returns:
        int: n choose k
    """
    n_f = math.factorial(n)
    k_f = math.factorial(k)
    n_minus_k_f = math.factorial(n - k)
    n_choose_k = n_f / (k_f * n_minus_k_f)
    return int(n_choose_k)

def get_len_all_ratios(symbols: List, k: int) -> int:
    """Get the length of all possible ratios of k symbols from the list of symbols. k is the
    number of symbols in the numerator and denominator

    Returns:
        int: Length of all possible ratios of n symbols
    """
    n = len(symbols)
    return n_choose_k(n_choose_k(n, k), 2)


def print_all_ratios(symbols: List, k: int) -> None:
    """Print all possible ratios of k symbols from the list of symbols. k is the
    number of symbols in the numerator and denominator

    Returns:
        None
    """
    all_ratios = get_all_ratios(symbols, k)
    for ratio in all_ratios:
        n, d = ratio
        # lexically sort the symbols
        n = sorted(n)
        d = sorted(d)
        numerator_str = ", ".join(n)
        denominator_str = ", ".join(d)

        line_len = max(len(numerator_str), len(denominator_str))

        print(numerator_str)
        print('-' * line_len)
        print(denominator_str)
        print()
