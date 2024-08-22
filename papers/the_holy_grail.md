### Ideal assumptions
In this part, we will consider ideal conditions and ideal assumptions. It is easier to reason based on first principles under ideal assumptions first, and then bring complexity later on.

In order for a trader to make profit, they need an instrument to trade, that provides a timeseries (a graph).

**In an idealized world, what would the perfect graph be? Such that anyone could make profit?** 
Many would answer a line with a high slope, perhaps even an exponential curve. For me, the ideal graph looks like a **pure sinusoid () with a high amplitude and high frequency**.
We known precisely where the high is (and when to sell), where the low is (and when to buy again), and we have a historical proof of its repeatability.

An aggressive strategy under such conditions would be to simply buy at the bottom and sell at the peak:
![perfect_sine_aggressive](https://github.com/user-attachments/assets/4e5bf744-9966-4c16-bb75-29dfab3a0ed1)

Under ideal assumptions, the amplitude of the sine wave represents the potential profit per trade, and the frequency represents the repeatability of this trade.

We will want to identify, or even [create instruments](https://github.com/doruirimescu/python-trading/blob/master/papers/mean_reversion_strategy.md) whose charts look as close as possible to a perfect sine wave.

### Realistic conditions
Once we add noise to our perfect sine wave, both the amplitude and the period of the sinusoid will become harder to predict. We can plot the mean, and the standard deviations above and below it. Since we do not know anymore where the peaks are going
to happen, we can instead think in terms of standard deviations. We can now buy when the price reaches the low std, and sell when the price reaches the high std.
![noisy_sine_wave](https://github.com/user-attachments/assets/ddb0aa95-0d9e-461d-a065-d2a4f36740eb)


It becomes clear now, that the unpredictibility in both amplitude and and period have a negative impact on our potential profit.

Two problems now arise: 
1. How to select, from a plethora of graphs, the one that most resembles a sine wave?
2. How to set the buy and sell levels such as to maximize profits?

### Appendix

### Generating a pure sine wave
```python
import math
import matplotlib.pyplot as plt

N_POINTS = 500
t = [i/N_POINTS for i in range(N_POINTS)]
w = 5
a = 1
y = [a*math.sin(2*math.pi*i*w) + a for i in t]

plt.plot(t, y)
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.grid()
plt.show()
```

### Generating a sine wave with noise
```python
import math
import random
import matplotlib.pyplot as plt

N_POINTS = 200
t = [i/N_POINTS for i in range(N_POINTS)]
w = 5
a = 1
y = []
for i in t:
    # add noise
    w_ = w + random.random()*2
    y.append(a*(math.sin(2*math.pi*i*w_) + a ))

mean = sum(y) / len(y)
std = math.sqrt(sum([(y_i - mean)**2 for y_i in y]) / len(y))
plt.plot(t, y)
plt.plot(t, [mean for _ in t], label='Mean', color='black')
plt.plot(t, [mean + std for _ in t], label='Mean + std', color='red')
plt.plot(t, [mean - std for _ in t], label='Mean - std', color='green')
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.legend(('Signal', 'Mean', 'Mean + std', 'Mean - std'))
plt.grid()
plt.show()
```
