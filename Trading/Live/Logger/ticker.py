from datetime import datetime
from Trading.Instrument.timeframes import *
import logging


class Ticker:
    """Ticker class which is used to determine if the time specified in timeframe has passed.
    Ticks every second.
    """

    def __init__(self, timeframe):
        self.validate(timeframe)
        self.timeframe = timeframe
        self.timeframe_seconds_ = TIMEFRAME_TO_MINUTES[timeframe]*60
        self.LOGGER = logging.getLogger('Ticker')

    def validate(self, timeframe):
        """Check if the timeframe is supported

        Args:
            timeframe (str): String which determines timeframe to tick.

        Raises:
            Exception: Timeframe not supported
        """
        if timeframe not in TIMEFRAMES:
            raise Exception("Timeframe not supported")

    def tick(self, test=None):
        """Check if the time has elapsed or not.

        Args:
            test (Mock datetime, optional): Used to mock the datetime.now() method. Defaults to None.

        Returns:
            bool: True if the time has passed, False otherwise.
        """

        now = datetime.now()
        if test is not None:
            now = test
        second = now.second
        minute = now.minute
        hour = now.hour
        day = now.day
        weekday = now.weekday()

        self.LOGGER.debug("Ticking... ")

        if second == 1:
            if(self.timeframe == '1m'):
                return True
            elif(self.timeframe == '5m' and (minute % 5 == 0)):
                return True
            elif(self.timeframe == '15m' and (minute % 15 == 0)):
                return True
            elif(self.timeframe == '30m' and (minute % 30 == 0)):
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

    def __enter__(self):
        return self

    def __del__(self):
        self.LOGGER.debug("Deleting ticker")
