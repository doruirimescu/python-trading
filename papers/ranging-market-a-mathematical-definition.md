## Variable Definitions

**$N$** — number of candles (time periods) in the scoring window.

**$H_i$, $L_i$, $C_i$** — high, low, and close price of candle $i$, for $i \in \{1, \ldots, N\}$.

**$P_k(X)$** — the $k$-th percentile of a sequence $X$.

---

## Shared Primitives

### Range Width $W$

The full observed span over the window:

$$
W = \max_{i \in [1,N]} H_i - \min_{i \in [1,N]} L_i
$$

### Diminished Range Width $W_x$

Outlier-resistant span, formed by trimming the extreme $x\%$ of highs and lows:

$$
p_{\text{high},x} = P_{100-x}(H_{1:N}), \qquad p_{\text{low},x} = P_{x}(L_{1:N})
$$

$$
W_x = p_{\text{high},x} - p_{\text{low},x}
$$

This filters single-candle wicks, but if the outliers are *recent*, the range may already be breaking out — use with care.

### Cumulative Intraday Movement $\Sigma$

The total vertical distance traveled by price across all candles:

$$
\Sigma = \sum_{i=1}^{N} (H_i - L_i)
$$

---

## Scorer 1 — `RangeScorer`

### Idea

Penalize price series whose highs and lows wander far from their own mean. A tight range means both highs and lows stay close to constant levels, so their **coefficient of variation** (CV) should be small.

### Definition

Let

$$
\mu_H = \frac{1}{N}\sum_{i=1}^{N} H_i, \qquad \sigma_H = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(H_i - \mu_H)^2}
$$

$$
\mu_L = \frac{1}{N}\sum_{i=1}^{N} L_i, \qquad \sigma_L = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(L_i - \mu_L)^2}
$$

Define the coefficient of variation for each series:

$$
\text{CV}_H = \frac{\sigma_H}{\mu_H}, \qquad \text{CV}_L = \frac{\sigma_L}{\mu_L}
$$

The score is:

$$
\boxed{S_1 = \frac{1}{\text{CV}_H + \text{CV}_L}}
$$

### Properties

- $S_1 \to \infty$ as both series approach a constant (perfect horizontal range).
- $S_1$ is dimensionless and scale-invariant (the mean normalization removes the absolute price level).
- **Weakness**: uses all data points with equal weight, so a single persistent outlier drags $\sigma_H$ or $\sigma_L$ upward, and a smooth linear trend can have low CV while not ranging at all.

---

## Scorer 2 — `RangeCoherenceMetric`

### Idea

A stock that spends most of its time traversing the full height of its range produces large candle bodies relative to the range width. The metric captures this **vertical density**: the sum of all candle spans as a fraction of the absolute range width, then normalized per candle.

### Definition

$$
W = \max_{i} H_i - \min_{i} L_i
$$

$$
S = \frac{\Sigma}{W} = \frac{\displaystyle\sum_{i=1}^{N}(H_i - L_i)}{W}
$$

The score is:

$$
\boxed{R = \frac{S}{N} = \frac{1}{N} \cdot \frac{\displaystyle\sum_{i=1}^{N}(H_i - L_i)}{W}}
$$

### Bounds

$S$ achieves its maximum when every candle spans the full range: $S_{\max} = N$, giving $R_{\max} = 1$.

$R \in (0, 1]$ for any non-degenerate window.

### Properties

- Elegant closed-form, single normalization step.
- Sensitive to absolute extremes: a single historical spike permanently inflates $W$, collapsing $R$ toward zero even if recent price action is clean.
- Has no directional awareness — a drift candle and a reversal candle contribute equally to $\Sigma$.

---

## Scorer 3 — `RobustRangeScorer`

### Idea

Combine three improvements over the first two scorers:

1. **Robust boundaries** via percentiles instead of absolute extremes.
2. **Oscillation measurement** — reward stocks that travel large multiples of the range height.
3. **Trend penalty** — discount any range whose center of mass drifts between the first and second half of the window.

### Step 1: Robust Boundaries

$$
R_{\text{sup}} = P_{90}(H_{1:N}), \qquad R_{\text{res}} = P_{10}(L_{1:N})
$$

$$
\Delta = R_{\text{sup}} - R_{\text{res}}
$$

Guard conditions (return $0$ immediately if either fails):

$$
\Delta \leq 0, \qquad \text{or} \qquad \frac{\Delta}{R_{\text{res}}} < 0.20
$$

The second guard rejects ranges that are too tight relative to the absolute price level (less than 20% of support), filtering noise and micro-consolidations.

### Step 2: Oscillation Score

$$
\text{Osc} = \frac{\Sigma}{\Delta} = \frac{\displaystyle\sum_{i=1}^{N}(H_i - L_i)}{\Delta}
$$

A value of $\text{Osc} = k$ means the stock has collectively traversed $k$ full range heights worth of movement. Higher is better for a mean-reversion trader.

### Step 3: Trend Penalty (Flatness Check)

Let $m = \lfloor N/2 \rfloor$. Define the half-window means of the close:

$$
\bar{C}_1 = \frac{1}{m}\sum_{i=1}^{m} C_i, \qquad \bar{C}_2 = \frac{1}{N-m}\sum_{i=m+1}^{N} C_i
$$

The normalized drift:

$$
\phi = \frac{|\bar{C}_1 - \bar{C}_2|}{\Delta}
$$

$\phi = 0$ for a perfectly flat range; $\phi = 1$ when the price center has shifted by one full range height between the two halves.

### Step 4: Final Score

$$
\boxed{S_3 = \frac{\text{Osc}}{1 + \phi} = \frac{\displaystyle\sum_{i=1}^{N}(H_i - L_i)}{\Delta \cdot (1 + \phi)}}
$$

The $+1$ in the denominator prevents division by zero and ensures that a perfectly flat range ($\phi = 0$) is not artificially penalized — a stock with zero drift receives its full oscillation score.

### Properties

- Increasing in $\Sigma$: more intraday movement inside the range raises the score.
- Decreasing in $\phi$: any diagonal drift directly reduces the score.
- Robust to single-candle spikes: the top and bottom 10% of wicks are excluded from boundary estimation.
- Not bounded above — $S_3$ grows with oscillation, so rankings are relative, not absolute.

---

## Improvements to `RangeCoherenceMetric` *(implemented)*

### The Core Problem

The original $R$ has two coupled failure modes:

1. **Denominator inflation** — a single spike candle maximises $W$, making the range look enormous and driving $R \to 0$ for an otherwise clean consolidation.
2. **Numerator inflation** — that same spike candle also contributes a large $(H_i - L_i)$ to $\Sigma$, partially offsetting (1) in an unpredictable way.

Fixing only the denominator (swapping $W \to W_x$) is therefore not sufficient: spike candles in the numerator can then exceed $W_x$, which breaks the $R \leq 1$ bound and distorts rankings.

### Robust Coherence Metric $R^*$

The fix replaces absolute boundaries with percentile boundaries **and** clips each candle's contribution to the interior of the robust range, so numerator and denominator use the same reference frame.

**Step 1 — Robust boundaries** (same as $W_x$ with $x = 10$):

$$
p_H = P_{90}(H_{1:N}), \qquad p_L = P_{10}(L_{1:N}), \qquad W^* = p_H - p_L
$$

**Step 2 — Clipped candle spans:**

$$
H_i^* = \min(H_i,\ p_H), \qquad L_i^* = \max(L_i,\ p_L)
$$

$$
c_i = \max\!\bigl(H_i^* - L_i^*,\ 0\bigr)
$$

Candles entirely outside the robust range yield $c_i = 0$; candles that partially overlap the range are trimmed to the overlap; candles fully inside the range are unchanged.

**Step 3 — Robust Coherence Metric:**

$$
\boxed{R^* = \frac{1}{N} \cdot \frac{\displaystyle\sum_{i=1}^{N} c_i}{W^*}}
$$

### Why This Preserves All Original Properties

Since $0 \leq c_i \leq W^*$ by construction:

$$
0 \leq \sum_{i=1}^{N} c_i \leq N \cdot W^* \implies R^* \in [0, 1]
$$

$R^* = 1$ when every candle spans the full robust range — the same maximum interpretation as the original $R = 1$. The only change is that outlier candles no longer distort either side of the fraction.

### Intuition for the Clipping

A spike candle that briefly exceeds the established range boundaries is, from a ranging perspective, not more valuable than a candle that exactly fills the range. Capping $c_i$ at $W^*$ reflects this: the spike is credited for full range traversal, not for distorting the scale.

### Comparison: $R$ vs $R^*$

| Property | Original $R$ | Proposed $R^*$ |
|---|---|---|
| Denominator | $W = \max H - \min L$ | $W^* = P_{90}(H) - P_{10}(L)$ |
| Numerator terms | $H_i - L_i$ (unbounded) | $c_i = \max(\min(H_i, p_H) - \max(L_i, p_L),\ 0)$ |
| Spike in denominator | Inflates $W$, collapses $R$ | Excluded via percentile |
| Spike in numerator | Inflates $\Sigma$, partially offsets (1) | Capped at $W^*$, effect is bounded |
| $R \in [0, 1]$ bound | Holds in theory; violated when $W \to W_x$ only | Always holds by construction |
| Directional awareness | None | None (unchanged) |

### Code

```python
def calculate(self, history: History):
    p_high = history.calculate_percentile(OHLC.HIGH, 90.0)
    p_low  = history.calculate_percentile(OHLC.LOW, 10.0)
    width  = p_high - p_low
    if width <= 0:
        return 0.0

    clipped = [max(min(h, p_high) - max(l, p_low), 0)
               for h, l in zip(history.high, history.low)]
    return sum(clipped) / (history.len * width)
```

### Remaining Limitation

$R^*$ still has no directional awareness: a drift candle and a reversal candle contribute equally to $\sum c_i$. If diagonal-trend rejection is needed, combine $R^*$ with the flatness penalty $\phi$ from `RobustRangeScorer`:

$$
R^{**} = \frac{R^*}{1 + \phi}, \qquad \phi = \frac{|\bar{C}_1 - \bar{C}_2|}{W^*}
$$

This yields a scorer with the bounded output of $R$ and the trend-rejection of $S_3$, at the cost of losing the clean $[0,1]$ upper bound (the denominator $> 1$ for any drifting window).

---

## Comparison Table

| Feature | `RangeScorer` ($S_1$) | `RangeCoherenceMetric` ($R$) | `RobustRangeScorer` ($S_3$) |
|---|---|---|---|
| **Primary Metric** | $1 / (\text{CV}_H + \text{CV}_L)$ | $\Sigma / (N \cdot W)$ | $\Sigma / (\Delta \cdot (1 + \phi))$ |
| **Boundary Method** | All data points (squared deviations from the mean) | Absolute $\max$ and $\min$ | Percentiles $P_{90}$ and $P_{10}$ |
| **Outlier / Spike Handling** | **Poor** — outliers inflate $\sigma$, dragging down the score via squared deviations | **Terrible** — a single spike permanently maximizes $W$, collapsing $R$ toward zero | **Excellent** — top and bottom 10% of wicks are excluded from $\Delta$ |
| **Detects False Ranges (Diagonal Trends)** | **Weak** — a smooth low-volatility linear trend has small CV yet is not a range | **Weak** — $R$ is blind to chronological order; it cannot see drift | **Strong** — $\phi$ directly measures the drift between first and second half means, and it enters the denominator |
| **Measures Ping-Pong Oscillation** | **No** — only penalizes dispersion; does not reward internal back-and-forth | **Partially** — $R$ captures relative vertical density but treats all candles equally regardless of direction | **Yes** — $\text{Osc} = \Sigma/\Delta$ rewards stocks that travel many multiples of the range height |
| **Scale Invariance** | Yes — CV is dimensionless | Yes — $R \in (0,1]$ for any price level | Partial — $S_3$ is dimensionless but unbounded; only meaningful in relative ranking |
| **Tight Range Guard** | None | None | Yes — discards windows where $\Delta / R_{\text{res}} < 0.20$ |
| **Upper Bound** | None (approaches $\infty$) | $R \leq 1$ | None (grows with oscillation) |
| **Ideal Chart Pattern** | Flat, low-volatility channels with small absolute deviation | Volatile price action filling a rigid container | Active, clean horizontal consolidations ready for mean-reversion trades |
