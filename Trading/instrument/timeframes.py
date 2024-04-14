from enum import Enum

class TIMEFRARME_ENUM(Enum):
    ONE_MINUTE = '1m'
    TWO_MINUTE = '2m'
    FIVE_MINUTE = '5m'
    FIFTEEN_MINUTE = '15m'
    THIRTY_MINUTE = '30m'
    SIXTY_MINUTE = '60m'
    ONE_HOUR = '1h'
    FOUR_HOUR = '4h'
    FIVE_HOUR = '5h'
    ONE_DAY = '1D'
    FIVE_DAY = '5D'
    ONE_WEEK = '1W'
    ONE_MONTH = '1M'
    THREE_MOTH = '3M'
assert TIMEFRARME_ENUM.ONE_MINUTE.value == '1m'

__all__ = ['TIMEFRAMES', 'TIMEFRAME_TO_MINUTES', 'TIMEFRARME_ENUM']

TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1D', '1W', '1M']
TIMEFRAME_TO_MINUTES = dict(zip(TIMEFRAMES, [1, 5, 15, 30, 60, 240, 1440, 10080, 43200]))
TIMEFRAMES_TO_NAME = dict(zip(TIMEFRAMES, ['1-min', '5-min', '15-min', '30-min', '1-hour',
                                            '4-hour', '1-day', '1-week', '1-month']))


class Timeframe:
    def __init__(self, period: str | TIMEFRARME_ENUM, client_type: str = "XTB") -> None:
        if isinstance(period, TIMEFRARME_ENUM):
            period = period.value
        if client_type == "XTB":
            self.timeframes = TIMEFRAMES
            self.timeframe_to_minutes = TIMEFRAME_TO_MINUTES
            self.timeframes_to_name = TIMEFRAMES_TO_NAME

        if period not in self.timeframes:
            raise ValueError(f"Timeframe period {period} is not supported")
        self.period = period

    def get_minutes(self) -> int:
        return self.timeframe_to_minutes[self.period]

    def get_seconds(self) -> int:
        return self.get_minutes() * 60

    def get_name(self) -> str:
        return self.timeframes_to_name[self.period]

    def __str__(self) -> str:
        return self.period
