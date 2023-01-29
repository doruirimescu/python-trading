import pytz
import datetime


def get_datetime_now_cet() -> datetime.datetime:
    return datetime.datetime.now(pytz.timezone('Europe/Berlin'))


def get_date_now_cet() -> datetime.date:
    """Gets today's date in Central European Time

    Returns:
        datetime.time: Today's date
    """
    datetime_now = get_datetime_now_cet()
    return datetime_now.date()
