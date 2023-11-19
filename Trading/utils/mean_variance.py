# A portfolio is in this case represented by a collection of
# returns and their weights.
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import math
import matplotlib.pyplot as plt

import itertools

def generate_tuples_itertools(n, step=0.05):
    possible_values = [round(i * step, 2) for i in range(int(1 / step) + 1)]
    all_combinations = itertools.product(possible_values, repeat=n)

    # Filter tuples that sum to 1
    return [t for t in all_combinations if round(sum(t), 2) == 1]

@dataclass
class AssetReturns:
    rates_of_return: List[float]
    name: Optional[str]

    def mean(self):
        return np.mean(self.rates_of_return)

    def variance(self):
        return np.var(self.rates_of_return)

    def standard_deviation(self):
        return math.sqrt(self.variance())

def asset_covariance(a1: AssetReturns, a2: AssetReturns):
    return np.cov(a1.rates_of_return, a2.rates_of_return, ddof=0)[0][1]

def asset_correlation(a1: AssetReturns, a2: AssetReturns):
    return np.corrcoef(a1.rates_of_return, a2.rates_of_return, ddof=0)[0][1]

@dataclass
class Portfolio:
    asset_returns: List[AssetReturns]
    weights: List[float]
    name: str = "Portfolio"

    def mean(self):
        return sum([asset.mean() * self.weights[i] for i, asset in enumerate(self.asset_returns)])

    def variance(self):
        variance = 0
        for i, ai in enumerate(self.asset_returns):
            for j, aj in enumerate(self.asset_returns):
                variance += self.weights[i] * self.weights[j] * asset_covariance(ai, aj)
        return variance

    def plot(self):
        possible_weights = generate_tuples_itertools(len(self.asset_returns))
        for weights in possible_weights:
            portfolio = Portfolio(
                [
                    AssetReturns(asset.rates_of_return, asset.name)
                    for asset in self.asset_returns
                ],
                weights
            )
            plt.scatter(portfolio.variance(), portfolio.mean(), c="blue")
        plt.xlabel("Variance")
        plt.ylabel("Mean")
        plt.title(self.name)
        plt.show()

# r1 = [0.5, 0.1, -0.1]
# r2 = [0, 0.3, -0.3]
# r3 = [0.1, 0.2, 0.7]

# a1 = AssetReturns(r1, "a1")
# a2 = AssetReturns(r2, "a2")
# a3 = AssetReturns(r3, "a3")

# p = Portfolio([a1, a2, a3], [0, 0, 0])
# p.plot()
