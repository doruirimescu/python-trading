__all__ = ['TIMEFRAMES', 'TIMEFRAME_TO_MINUTES']
TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1D', '1W', '1M']
TIMEFRAME_TO_MINUTES = dict(zip(TIMEFRAMES, [1, 5, 15, 30, 60, 240, 1440, 10080, 43200]))
TIMEFRAMES_TO_NAME = dict(zip(TIMEFRAMES, ['1-min', '5-min', '15-min', '30-min', '1-hour',
                                            '4-hour', '1-day', '1-week', '1-month']))

class Timeframe:
    def __init__(self, period: str) -> None:
        if period not in TIMEFRAMES:
            raise ValueError(f"Timeframe period {period} is not supported")
        self.period = period

    def get_minutes(self) -> int:
        return TIMEFRAME_TO_MINUTES[self.period]

    def get_name(self) -> str:
        return TIMEFRAMES_TO_NAME[self.period]

    def __str__(self) -> str:
        return self.period
