from Trading.config.config import TIMEZONE
import pytz
import datetime


def get_datetime_now_cet() -> datetime.datetime:
    return datetime.datetime.now(pytz.timezone(TIMEZONE))


def get_datetime_from_now_cet(
    days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0
) -> datetime.datetime:
    return get_datetime_now_cet() + datetime.timedelta(
        days=days, hours=hours, minutes=minutes, seconds=seconds
    )
# print(get_datetime_from_now_cet(days=-1, hours=-2))


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
