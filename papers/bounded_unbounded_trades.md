# Bounded and unbounded trades
In this paper, we will attempt to categorize trades and their risk scores by analyzing their entry and exit conditions. We shall introduce the following terms: bounded, unbounded, soft-bound, hard-bounded.

* A trade's entry condition is a set of logical rules, which, if evaluated to true, result in the execution of the trade.
* A trade's exit condition is a set of logical rules, which, if evaluated to true, result in the closing of the trade. We can further categorize the exit conditions into two categories: stop loss (denoted by L) and take profit (P).
* A stop loss (L) is an exit condition, thus a set of logical rules which, if evaluated to true, result in the closing of the trade, resulting in a loss.
* A take profit (P) is an exit condition, thus a set of logical rules which, if evaluated to true, result in the closing of the trade, resulting in a profit.

### Unbounded trades
Unbounded (U) trades do not have an exit condition for the loss, profit, or both. Trades which, once entered, have no predefined conditions for an exit.
This can often end up in locked or realized capital losses.

### Bounded trades
Bounded trades have a defined exit condition for the loss, profit, or both. We can further categorize bounded trades into: soft-bounded (S) and hard-bounded (H) exit conditions, such that:
* soft-bounded (S) is a condition that depends on the evolution of the market, after the trade has been entered. For example, a certain price action pattern, piece of news or a candlestick pattern can indicate the condition for exiting the trade, which cannot be predicted prior to entering.

* hard-bounded (H) is a condition that is pre-determined before the trade has been entered. This can give an exact idea about the risk to reward ratio, and cannot lead into locking or losing large amounts of capital for a long amount of time. For example, a price target.


## Risk categories
We now have the necessary vocabulary make the following definitions:

* **ULUP** - unbounded stop loss, unbounded take profit. A trade which, once entered, has no conditions whatsoever for an exit. Examples: buying a stock because it is cheap, long-term investing in a popular index such as S&P 500 without a clear exit strategy. The typical "investing" scenario, where the investor has no actual clue as to when to declare the investment a failure and take what's left, or when to declare the investment a success and collect the profits.
* **ULSP** - unbounded loss, soft-bounded profit
* **ULHP** - unbounded loss, hard-bounded profit

* **SLUP** - soft-bounded loss, unbounded profit
* **SLSP** - soft-bounded loss, soft-bounded profit
* **SLHP** - soft-bounded loss, hard-bounded profit

* **HLUP** - hard-bounded loss, unbounded profit
* **HLSP** - hard-bounded loss, soft-bounded profit
* **HLHP** - hard-bounded loss, hard-bounded profit

## Risk scores
We shall attempt to create a scoring system, starting from the following premises:
* The higher score, the riskier the trade
* Unbounded is the riskiest type of trade
* Soft-bounded is a less risky type of trade
* Hard-bounded is the least risk-presenting type of trade
* A profit has the potential of turning into a loss.

| Risk Score | Risk Class | Abbreviation | Name                                   | Loss Description                                                                       | Profit Description                                                |
|------------|------------|--------------|----------------------------------------|----------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| 9          | High       | ULUP         | Unbounded Loss,  Unbounded Profit      | Unbounded losses can lead to the termination of the account.                           | Unbounded profits have the highest  risk of turning into losses.  |
| 8          | High       | ULSP         | Unbounded Loss,  Soft-Bounded Profit   | Unbounded losses can lead to the termination of the account.                           | Soft-bounded profits have a moderate risk of turning into losses. |
| 7          | High       | ULHP         | Unbounded Loss, Hard-Bounded Profit    | Unbounded losses can lead to the termination of the account.                           | Hard-bounded profits have a low risk of turning into losses.      |
| 6          | Medium     | SLUP         | Soft-Bounded Loss, Unbounded Profit    | Soft-bounded losses have a moderate risk of leading to the termination of the account. | Unbounded profits have a high risk of turning  into losses.       |
| 5          | Medium     | SLSP         | Soft-Bounded Loss, Soft-Bounded Profit | Soft-bounded losses have a moderate risk of leading to the termination of the account. | Soft-bounded profits have a medium risk of turning into lossesm   |
| 4          | Medium     | SLHP         | Soft-Bounded Loss, Hard-Bounded Profit | Soft-bounded losses have a moderate risk of leading to the termination of the account. | Hard-bounded profits have a low risk of turning into losses.      |
| 3          | Low        | HLUP         | Hard-Bounded Loss, Unbounded Profit    | Hard-bounded losses have a low risk of leading to account termination.                 | Unbounded profits have a high risk of turning  into losses.       |
| 2          | Low        | HLSP         | Hard-Bounded Loss, Soft-Bounded Profit | Hard-bounded losses have a low risk of leading to account termination.                 | Soft-bounded profits have a medium risk of turning into losses.   |
| 1          | Low        | HLHP         | Hard-Bounded Loss, Hard-Bounded Profit | Hard-bounded losses have a low risk of leading to account termination.                 | Hard-bounded profits have a low risk of turning into losses.      |
