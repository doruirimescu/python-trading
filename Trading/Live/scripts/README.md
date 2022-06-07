Here are the main scripts that enable you to live trade, ping the trading server or log real-time market data from investing.com analyses.

If you have not already, create a .env file
with the following variables defined:

```
XTB_USERNAME="your-xtb-account-number-ex 14239204"
XTB_PASSWORD="password"
```

## Trading live
For live trading, check `live_trader.py`. Run as follows:
`python3 live_trader.py -s BITCOIN -t 1m`

For more information on available instrument names, check the `Instrument` package.

## Pinging xtb server
`log_server_tests.py`

## Logging instrument data
TBD
