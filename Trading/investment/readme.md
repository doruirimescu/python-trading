## Investment model
Investments are modelled as data structures in python [here](https://github.com/doruirimescu/python-trading/blob/master/Trading/model/investment.py).

```python
class PriceQuote(BaseModel):
    price: float
    time: Optional[datetime] = None
    currency: Optional[str] = None

class Investment(BaseModel):
    name: str
    symbol: str
    entry_price: PriceQuote
    exit_price: Optional[PriceQuote] = None
    volume: float
    profit: Optional[float] = None
    other: Optional[dict] = None
```

Various things can be modeled as investments, but for now we focus on precious metals and etf buying.

## Precious Metal Investment Tracking
Keep track of your precious metal investments. 

All you need to do is to create a json file with the data of your precious metal investments, then run a script which summarizes your investments.

Please take your time to familiarize yourself 

Here is a snippet of how your json could look like. You should make one json file per precious metal type. For example, for silver investments, `silver.json` could be:
```json
[
    {
        "entry_price": {
            "currency": "eur",
            "price": 31.2,
            "time": "2023-11-03 00:00:00"
        },
        "exit_price": null,
        "name": "6 silver spoons",
        "other": {
            "location": "Finland",
            "market_price_at_purchase": 0.7,
            "vendor": null
        },
        "profit": null,
        "purity": 0.813,
        "symbol": "silver",
        "type": "tableware",
        "volume": 1.0,
        "weight_g": 50.0
    },

    {
        "entry_price": {
            "currency": "eur",
            "price": 180.0,
            "time": "2023-09-15 00:00:00"
        },
        "exit_price": null,
        "name": "bullion from turkey",
        "other": {
            "location": "Turkey",
            "market_price_at_purchase": 0.7,
            "vendor": null
        },
        "profit": null,
        "purity": 0.999,
        "symbol": "silver",
        "type": "bullion",
        "volume": 1.0,
        "weight_g": 250.0
    }
]
```

Then, run the script: `python3 precious_metal.py --path silver_example.json --current_market_price_g 0.9`.

Your summary comes up:
```txt
Metal: silver
Total invested: 211.20 eur
Total silver weight: 290.40 g
Total (impure) weight: 300.00 g
Total purity: 0.97
Average paid price per pure silver gram: 0.727 eur/g
Average market price per pure silver gram: 0.700 eur/g
Current market value: 261.36 eur
Current profit: 50.16 eur
```
