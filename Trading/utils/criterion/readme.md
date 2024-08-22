# Numerical and logical expression wrapper

Wrapper for logical expressions that can be debugged, printed, enabled and disabled.

Here is a practical example:
```python
from Trading.utils.criterion.expression import Numerical, and_
import operator

payout_criterion = Numerical(
    "Payout ratio", operator.lt, payout_ratio, max_payout_ratio
)
yield_criterion = Numerical(
    "Dividend yield", operator.ge, dividend_yield, min_yield
)
debt_criterion = Numerical(
    "Debt-to-equity ratio", operator.le, debt_equity, max_debt_equity
)
roe_criterion = Numerical("Return on equity", operator.ge, roe, min_roe)
free_cashflow_criterion = Numerical(
    "Free cash flow", operator.ge, free_cashflow, min_free_cashflow
)
criteria = and_(
    payout_criterion,
    yield_criterion,
    debt_criterion,
    roe_criterion,
    free_cashflow_criterion,
)
print(criteria.formatted())
```

*Console output:*
```txt
( (Payout ratio 250.0 < 80 False) & 
( (Dividend yield 12.93 >= 2.0 True) & 
( (Debt-to-equity ratio 1.16 <= 0.5 False) & 
( (Return on equity 4.45 >= 10.0 False) & 
(Free cash flow 200260256 >= 10000000.0 True) False) False) False) False)
```
Whenever you have complex criteria in your program, you should really use this framework. 

Calling `.debug` on a criterion will list the conditions that make it evaluate to `False`. 

By inspecting this output, you can painlessly debug why your criteria doesn't evaluate to `True` when expected.

```python
import operator
roe = Threshold("Return on Equity: ", operator.ge, 10.0)
# (Return on Equity: X >= 10.0 False)
div_yield = Threshold("Dividend yield: ", operator.ge, 5.0)
print(roe)
# (Dividend yield: X >= 5.0 False)
combined = roe & div_yield
print(combined)
# ((Return on Equity: X >= 10.0 False) & (Dividend yield: X >= 5.0 False) False)
roe.value = 15.0
div_yield.value = 7.0
print(combined)
# ((Return on Equity: 15.0 >= 10.0 True) & (Dividend yield: 7.0 >= 5.0 True) True)

roe.value = 3.0
print(combined.debug())
# (Return on Equity: 3.0 >= 10.0 False)
roe.disable()
print(combined)
# (Dividend yield: 7.0 >= 5.0 True)
```
