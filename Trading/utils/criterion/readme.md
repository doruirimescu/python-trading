# Numerical and logical expression wrapper
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
