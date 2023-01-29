import pytz
from datetime import datetime


def get_datetime_now_cet() -> datetime:
    return datetime.now(pytz.timezone('Europe/Berlin'))


def get_date_now_cet() -> datetime.time:
    datetime_now = get_datetime_now_cet()
    return datetime_now.date()
