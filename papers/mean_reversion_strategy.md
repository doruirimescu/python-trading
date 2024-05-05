# Risk management considerations
### Wealth cycles and mean reversion
During my research and adventures with trading, I have noticed one thing: predicting the future (of an asset price) is hard. ["Past performance is no guarantee of future results."](https://russellinvestments.com/us/blog/past-performance-no-guarantee-future-results).
In principle, this means that by just looking at the past of an asset's price we cannot evaluate if it is now underpriced or overpriced. However, while educating myself on the topic of precious metals and monetary
history, I came across Mike Maloney's idea of [wealth cycles](https://youtu.be/l-knwwD-PZc). The idea is simple: instead of plotting the price of an asset, plot the ratio between two asset prices. 
In this way, one can determine which asset is overpriced in relation to the other. This works especially well with assets that have existed for a while, and which have been historically somewhat correlated. 
We can look at gold to silver ratio, gold to real estate ratio, real estate to oil ratio, or even gold to S&P 500 ratio in order to have a better understanding of which asset is more overpriced in relation to the another. Mathematically, this makes sense, as any 
linear component of a trend gets cancelled.

![Selection_2204](https://github.com/doruirimescu/python-trading/assets/7363000/7ab9e44f-adcb-4e16-969e-c09b1947bcaa)
*[Gold to Silver Ratio - 100 Year Historical Chart](https://www.macrotrends.net/1441/gold-to-silver-ratio)*

This kind of framing gives rise to the idea of a "mean reversion strategy": by looking at the historical ratio, we can determine when the asset in the numerator is overvalued (when the ratio is significantly
higher above its historical average), sell it and buy the asset in the denominator. Conversely, when the ratio is significantly lower than the historical average, we can sell the asset in the denominator
and buy the asset from the numerator. 

For example, when the gold to silver ratio goes above 80, we sell the gold and buy silver. When the ratio reaches below 20, we sell the silver and buy gold. 

### Benefits
* We 

### Characteristics
It is immediately apparent that the ideal "wealth cycle" has the following characteristics:
* High frequency. We do not want to wait too long until the cycle reverses, and we can perform a transaction
