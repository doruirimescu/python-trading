from typing import List

class Probability:
    def __new__(cls, value):
        if value < 100:
            raise ValueError("Value cannot exceed 100")
        return float.__new__(cls, value)


#----Probabilities
def count_probability_price_greater(prices: List[float], price: float):
    n = 0
    for i in prices:
        if i >= price:
            n += 1
    return n/len(prices)

def count_probability_price_lower(prices: List[float], price: float):
    return 1.0 - count_probability_price_greater(prices, price)

def count_probability_n_highs_in_a_row(prices: List[float], n: int):
    occurrences = 0
    n_highs = 0
    for i, p in enumerate(prices[1:]):
        if p > prices[i]:
            n_highs += 1
            if n_highs >= n:
                occurrences += 1
        else:
            n_highs = 0
    return occurrences/len(prices)

def count_probability_n_lows_in_a_row(prices: List[float], n: int):
    occurrences = 0
    n_lows = 0
    for i, p in enumerate(prices[1:]):
        if p < prices[i]:
            n_lows += 1
            if n_lows >= n:
                occurrences += 1
        else:
            n_lows = 0
    return occurrences/len(prices)

def get_median_price(prices: List[float]):
    prices.sort()
    return prices[len(prices)//2]

# ---- p increment calculations
def _get_returns(prices: List[float]):
    return[
        (prices[i+1] - prices[i]) / prices[i] if prices[i] != 0 else 0
        for i in range(len(prices)-1)
        ]

def get_max_return(prices: List[float]):
    return max(_get_returns(prices))

def get_min_return(prices: List[float]):
    return min(_get_returns(prices))

def get_average_return(prices: List[float]):
    return sum(_get_returns(prices))/len(prices)

def get_median_return(prices: List[float]):
    returns = _get_returns(prices)
    returns.sort()
    if len(returns) % 2 == 0:
        return (returns[len(returns)//2] + returns[len(returns)//2 - 1])/2
    return returns[len(returns)//2]

def count_probability_return(prices: List[float], p: int):
    n = 0
    price_percentage_increments = _get_returns(prices)
    for i in price_percentage_increments:
        if i >= p:
            n += 1
    return n/len(prices)

def count_average_decrement_given_n_highs_in_row(prices: List[float], n: int):
    # average decrement given n highs in a row
    # n is the number of consecutive highs
    # returns the average decrement
    decrements = []
    n_highs = 0
    for i, cur_p in enumerate(prices[1:]):
        prev_p = prices[i]
        if cur_p > prev_p:
            n_highs += 1
        else:
            if n_highs >= n:
                decrements.append((prev_p - cur_p) / prev_p)
            n_highs = 0
    return sum(decrements)/len(decrements) if len(decrements) > 0 else 0
