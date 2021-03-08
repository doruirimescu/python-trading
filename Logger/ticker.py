import time
from datetime import datetime
from datetime import timedelta

from timeframes import TIMEFRAMES
from timeframes import TIMEFRAME_TO_MINUTES
import time

class Ticker:
    def __init__(self, timeframe):
        self.validate(timeframe)
        self.timeframe = timeframe
        self.timeframe_seconds_ = TIMEFRAME_TO_MINUTES[timeframe]*60

    def validate(self, timeframe):
        if timeframe not in TIMEFRAMES:
            raise Exception("Timeframe not supported")

    def tick(self, test=None):
        now = datetime.now()
        if test is not None:
            now = test
        second = now.second
        minute = now.minute
        hour = now.hour
        day = now.day
        weekday = now.weekday()

        if second == 1:
            if(self.timeframe == '1m'):
                return True
            elif(self.timeframe == '5m' and (minute % 5 == 0)):
                return True
            elif(self.timeframe == '15m' and (minute % 15 == 0)):
                return True
            elif(self.timeframe == '30m' and (minute % 30  == 0)):
                return True
            elif(self.timeframe == '1h' and (minute == 0)):
                return True
            elif(self.timeframe == '5h' and (hour % 5 == 0 and minute == 0)):
                return True
            elif(self.timeframe == '1D' and hour == 12 and minute == 0):
                return True
            elif(self.timeframe == '1W' and weekday == 0 and hour == 12 and minute == 0):
                return True
        return False

    def isTradingNow(self, symbol):
        #TODO find out if symbol is trading otherwise don't tick
        pass
