from datetime import datetime
from Trading.instrument.timeframes import *
from Trading.utils.time import get_datetime_now_cet
from typing import Optional
import logging


class Ticker:
    """Ticker class which is used to determine if the time specified in timeframe has passed.
    Ticks every second.
    """

    def __init__(self, timeframe: TIMEFRARME_ENUM):
        self.validate(timeframe)
        self.timeframe = timeframe
        self.timeframe_seconds_ = TIMEFRAME_TO_MINUTES[timeframe.value]*60
        self.LOGGER = logging.getLogger('Ticker')

    def validate(self, timeframe: TIMEFRARME_ENUM):
        """Check if the timeframe is supported

        Args:
            timeframe (str): String which determines timeframe to tick.

        Raises:
            Exception: Timeframe not supported
        """
        if timeframe.value not in TIMEFRAMES:
            raise Exception("Timeframe not supported")

    def tick(self, test=Optional[datetime]):
        """Check if the time has elapsed or not.

        Args:
            test (Mock datetime, optional): Used to mock the datetime.now() method. Defaults to None.

        Returns:
            bool: True if the time has passed, False otherwise.
        """

        now = get_datetime_now_cet()
        if test is not None:
            now = test
        second = now.second
        minute = now.minute
        hour = now.hour
        weekday = now.weekday()

        self.LOGGER.debug("Ticking... ")

        if second == 1:
            if(self.timeframe == TIMEFRARME_ENUM.ONE_MINUTE):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.FIVE_MINUTE and (minute % 5 == 0)):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.FIFTEEN_MINUTE and (minute % 15 == 0)):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.THIRTY_MINUTE and (minute % 30 == 0)):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.ONE_HOUR and (minute == 0)):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.FOUR_HOUR and (hour % 4 == 0 and minute == 0)):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.ONE_DAY and hour == 12 and minute == 0):
                return True
            elif(self.timeframe == TIMEFRARME_ENUM.ONE_WEEK and weekday == 0 and hour == 12 and minute == 0):
                return True
        return False

    def __enter__(self):
        return self

    def __del__(self):
        self.LOGGER.debug("Deleting ticker")
