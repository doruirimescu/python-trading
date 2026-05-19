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

TIMEFRAMES_Y_FINANCE = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']

TIMEFRAME_TO_MINUTES = dict(zip(TIMEFRAMES_Y_FINANCE, [1, 5, 15, 30, 60, 240, 1440, 10080, 43200]))
TIMEFRAMES_TO_NAME = dict(zip(TIMEFRAMES_Y_FINANCE, ['1-min', '5-min', '15-min', '30-min', '1-hour',
                                            '4-hour', '1-day', '1-week', '1-month']))

TIMEFRAMES_TO_NAME_Y_FINANCE = dict(zip(TIMEFRAMES_Y_FINANCE, ['1-min', '2-min', '5-min', '15-min', '30-min', '60-min',
                                                              '90-min', '1-hour', '1-day', '5-day', '1-week', '1-month',
                                                              '3-month']))
TIMEFRAME_TO_MINUTES_Y_FINANCE = dict(zip(TIMEFRAMES_Y_FINANCE, [1, 2, 5, 15, 30, 60, 90, 60, 1440, 7200, 10080, 43200, 129600]))
class Timeframe:
    def __init__(self, period: str | TIMEFRARME_ENUM, client_type: str = "yfinance") -> None:
        if isinstance(period, TIMEFRARME_ENUM):
            period = period.value
        if client_type == "yfinance":
            self.timeframes = TIMEFRAMES_Y_FINANCE
            self.timeframe_to_minutes = TIMEFRAME_TO_MINUTES_Y_FINANCE
            self.timeframes_to_name = TIMEFRAMES_TO_NAME_Y_FINANCE
        else:
            raise ValueError(f"Client type {client_type} is not supported")

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
