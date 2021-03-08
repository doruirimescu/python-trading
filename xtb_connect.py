import argparse
import getpass

from XTBApi.api import Client
from datetime import datetime
from datetime import timedelta
from candle import Candle
from candleCsvWriter import CandleCsvWriter

from investing_candlestick import PatternAnalyzer
from investing_candlestick import PatternAnalysis
from investing_candlestick import PatternReliability

from investing_technical import TechnicalAnalyzer
from investing_technical import TechnicalAnalysis

import time
import timeframes
class Session:
    def __init__(self):
        parser = argparse.ArgumentParser(description='Login to xtb.')
        parser.add_argument('-u', dest='username', type=str, required=True)
        args = parser.parse_args()
        self.username = args.username    # 11989223
        self.password = getpass.getpass()

        # # FIRST INIT THE CLIENT
        self.client = Client()

    def login(self):
        # # THEN LOGIN
        self.client.login(self.username, self.password, mode="demo")
        return self.client

    def logout(self):
        self.client.logout()

class DataLogger:
    def __init__(self, symbol, timeframe, windowsize = 20):
        self.symbol = symbol
        self.timeframe = timeframe
        self.windowsize = windowsize
        self.session = Session()
        self.client = self.session.login()

        # # Get last WINDOW_SIZE candles
        hist = self.client.get_lastn_candle_history(symbol, timeframes.TIMEFRAME_TO_MINUTES[self.timeframe] * 60, self.windowsize)
        print("-------------")
        print(hist)

        self.candle_dictionary = dict()
        for h in hist:
            open    = h['open']
            high    = h['high']
            low     = h['low']
            close   = h['close']
            date    = datetime.fromtimestamp(h['timestamp'])
            candle = Candle(open, high, low, close, date)
            candle.setTechnicalAnalysis("")
            candle.setCandlestickAnalysis(PatternAnalysis())
            self.candle_dictionary[date] = candle

        self.__updatePatterns()

        for key in self.candle_dictionary:
            CandleCsvWriter(self.symbol, self.timeframe, self.candle_dictionary[key])

    def mainLoop(self, looprate_seconds, stopDate):
        while datetime.now() < stopDate:
            time.sleep(looprate_seconds)
            self.loopOnce()
        self.session.logout()

    def loopOnce(self):
        # 1. Get the latest candle
        h = self.client.get_lastn_candle_history(self.symbol, timeframes.TIMEFRAME_TO_MINUTES[self.timeframe] * 60, 1)[0]
        open    = h['open']
        high    = h['high']
        low     = h['low']
        close   = h['close']
        date    = datetime.fromtimestamp(h['timestamp'])

        # 2. If candle not in dictionary, update dictionary with new candle
        if date in self.candle_dictionary:
            print("Candle already in dictionary")
        else:
            print("Inserting new candle into dictionary")
            new_candle = Candle(open, high, low, close, date)

            # 3. Update candlestick tech and patterns
            inv_tech = TechnicalAnalyzer()
            analysis = inv_tech.analyse(self.symbolToInvesting(), self.timeframe)
            new_candle.setTechnicalAnalysis(analysis.name)
            self.candle_dictionary[date] = new_candle

            # 4. Remove oldest candle from dict
            oldest_key = list(self.candle_dictionary.keys())[0]
            oldest_candle = self.candle_dictionary.pop(oldest_key)

            # 5. Print oldest candle to file
            CandleCsvWriter(self.symbol, self.timeframe, oldest_candle)

    def __updatePatterns(self):
        # # Get last candlestick patterns and match to candles
        i = PatternAnalyzer()
        candle_patterns = i.analyse(self.symbolToInvesting(), self.timeframe)
        for pattern in candle_patterns:
            print(pattern.date)
            if pattern.date in self.candle_dictionary:
                current_reliability = self.candle_dictionary[pattern.date].getCandlestickAnalysis().reliability

                if pattern.reliability is PatternReliability.HIGH:
                    self.candle_dictionary[pattern.date].setCandlestickAnalysis(pattern)

                elif pattern.reliability is PatternReliability.MEDIUM and current_reliability is PatternReliability.LOW:
                    self.candle_dictionary[pattern.date].setCandlestickAnalysis(pattern)

    def symbolToInvesting(self):
        if self.symbol is "BITCOIN":
            return "BTCUSD"
        elif self.symbol is "ETHEREUM":
            return "ETHUSD"
        else:
            return self.symbol

data_logger = DataLogger('BITCOIN', '30m', 100)
#data_logger.mainLoop(30*60, datetime.now() + timedelta(hours=10))





# # CHECK IF MARKET IS OPEN FOR EURUSD
# client.check_if_market_open(["EURUSD"])

# # BUY ONE VOLUME (FOR EURUSD THAT CORRESPONDS TO 100000 units)
# #client.open_trade('buy', "EURUSD", 1)

# # SEE IF ACTUAL GAIN IS ABOVE 100 THEN CLOSE THE TRADE
# trades = client.update_trades() # GET CURRENT TRADES

# trade_ids = [trade_id for trade_id in trades.keys()]
# for trade in trade_ids:
#     actual_profit = client.get_trade_profit(trade) # CHECK PROFIT
#     if actual_profit >= 100:
#         client.close_trade(trade) # CLOSE TRADE
# # CLOSE ALL OPEN TRADES
# client.close_all_trades()
