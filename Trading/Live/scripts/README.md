Here are the main scripts that enable you to live trade, ping the trading server or log real-time market data from investing.com analyses or the xtb platform. These scripts put together all the puzzle pieces from the other folders in order to provide useful automation to the trader.

## You will need the following `.env` files:


If you have not already, create a .env file in this folder,
with the following variables defined:

```.env
# XTB configurations
XTB_USERNAME="12345678"
XTB_PASSWORD="xtbpwd"
XTB_MODE="demo-or-real"

# Email configurations
EMAIL_SENDER="sender@example.com"
EMAIL_PASSWORD="gmail-app-password"
EMAIL_RECIPIENTS=["recipient@example.com"]

# Program configurations
MONITOR_FOREX_TRADE_SWAPS_ONCE="True"

```

## Trading live
For live trading, check `live_trader.py`. Run as follows:
`python3 live_trader.py -s BITCOIN -t 1m`

For more information on available instrument names, check the `instrument` package.

## Pinging xtb server
`log_server_tests.py`

## Logging instrument data
TBD

## Monitoring swaps on open forex trades
`python3 monitor_forex_trade_swaps.py` will send an e-mail every morning at 7 AM with the daily swap report of your current active trades, and it will anounce by email if the following night one or more of the swaps will become negative.
