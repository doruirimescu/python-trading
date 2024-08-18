# A Quantitative Approach to Selecting Stocks in a Ranging Market

## Abstract
This paper presents a systematic approach to identifying and selecting stocks that have been ranging within a specific price band over a given period. 
The strategy aims to buy stocks that are near the bottom of their range, with the expectation of a rebound within the range. 
A Python-based methodology is used to screen potential candidates based on their historical price behavior, followed by a qualitative assessment of their 
financial strength to enhance the probability of successful trades.

## Introduction
The concept of range trading is based on the observation that some stocks tend to trade within a defined price range over time. 
This paper introduces a method to systematically identify such stocks and evaluate their potential as profitable trading opportunities. 
We describe a Python-based strategy to select stocks that have been ranging for a defined period and are positioned near the bottom of this range. 
We then refine this selection through a visual and financial analysis.

## Methodology

### Stock Selection Criteria
We define the criteria for selecting candidate stocks as follows:

* **Ranging Behavior:** Stocks must have been ranging within a defined price range for the past n months.
* **Position Within the Range:** The stock's current price must be within p% above the bottom of this range to be considered a buying opportunity.
* **Historical Price Comparison:** The stock's current price must be greater than its price y years ago, ensuring long-term growth potential.

### Ranking Stocks by Ranging Behavior
To quantify how well a stock has been ranging, we introduce a ranking function. 
The function calculates a rank which is meaningless on its own, but can be used to compare and order candidate stocks.
```python3
def calculate_rank(history: History, periods: int):
    # calculate how close to a perfect range the last periods are
    # 0 means perfect range, 1 means no range
    max_of_last_periods = max(history.high[-periods:])
    min_of_last_periods = min(history.low[-periods:])
    
    range_size = max_of_last_periods - min_of_last_periods
    
    sum_of_ranges = 0
    for h, l in zip(history.high[-periods:], history.low[-periods:]):
        sum_of_ranges += abs(h - l)
    return (range_size * periods - sum_of_ranges) / range_size

```
This function is used to rank stocks based on how close they are to a perfect range over the defined period. 
The stocks are then ordered by their rank, and only the top 30 stocks are selected for further analysis.

### Visual and Qualitative Analysis
After the quantitative screening, a visual analysis of the stock charts is conducted. 
We look for stocks that have a potential return of at least 8% within the existing range. 
Stocks that do not meet this criterion are excluded from further consideration.
<p align="center">
    <img src="https://github.com/user-attachments/assets/26de2431-13de-48d2-8fb7-3a8d228c0184" alt="Ranging stock" width="40%" />
</p>

<p align="center">
    <em>Ranging stock selected for visual inspection. One candle bar represents one month.</em>
</p>

### Financial Strength Evaluation
To increase the likelihood of a successful range-bound trade, we evaluate the financial strength of 
the shortlisted stocks. We use metrics such as:

* **Gurufocus Score:** A comprehensive measure of a company's overall financial health.
* **Alphaspread Solvency:** A metric indicating a company's ability to meet its long-term debt obligations.
Only stocks that exhibit strong financial health are considered viable candidates for this ranging strategy.

### Take profit selection
A reasonable take profit target should be selected well within the range, that could be achieved within some months.

## Selection and trade execution
Once a set of stocks has been selected for execution, it should be added to a list of monitored alarms.
