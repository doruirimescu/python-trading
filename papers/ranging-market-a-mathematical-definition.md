### Variable Definitions and Renaming:

1. **Range Size N:**  
  Number of candles (e.g., time periods) over which the range is assessed.
   
2. **Range Width W:**  
  The range's "width," defined as the difference between the maximum high and minimum low over the period N.
   
$$ W=max( H_{t} |t\in [ 1,N]) -min( L_{t} |t\in [ 1,N]) $$

3. **Diminished range width Wx:**
  The Diminished Range Width accounts for the exclusion of outlier price values by considering only the x% percentile of the high and low price data. The mathematical definition is as follows:

  $$
  p_{high,\ x} =Percentile_{100-x}( High_{1:N})
  $$
  
  $$
  p_{low,\ x} =Percentile_{x}( Low_{1:N})
  $$
  
  $$
  W_{x}=p_{high,\ x} -p_{low,\ x}
  $$

4. **Range Coherence Metric R:**  
  A normalized metric indicating how well-defined the range is, scaled to a maximum of 1.

Define S as:
  
  $$
  S = \sum_{i=1}^{N}\frac{H_{i} - L_{i}}{W},
  $$
  
  With the maximum value that it can possibly take:
  
  $$
  max_{s}(S) = N
  $$
  
  Then, the metric R is:
  
  $$
  R = \frac{S}{N},
  $$
  
  With the maximum value that R can possibly take:
  
  $$
  max_{r}(R) = 1
  $$

```python3
def calculate(self, history: History):
    # Compute the x% percentile of the high and low
    p_high = history.calculate_percentile(OHLC.HIGH, 100 - self.x_percent)
    p_low = history.calculate_percentile(OHLC.LOW, self.x_percent)

    # Calculate the diminished range width
    width = p_high - p_low

    # sum over high - low for each candle
    s = sum([h - l for h, l in zip(history.high, history.low)]) / width

    n = history.len
    return s / n
```
