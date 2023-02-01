from Trading.config.config import TIMEZONE
import pytz
import datetime
import math


def get_datetime_now_cet() -> datetime.datetime:
    return datetime.datetime.now(pytz.timezone(TIMEZONE))


def get_date_now_cet() -> datetime.date:
    """Gets today's date in Central European Time

    Returns:
        datetime.time: Today's date
    """
    datetime_now = get_datetime_now_cet()
    return datetime_now.date()


def get_seconds_to_next_date(next_date: datetime.datetime):
    today = get_datetime_now_cet()
    if today > next_date:
        next_date = datetime.timedelta(days=1) + next_date
    dt = next_date - today
    return dt.total_seconds()
