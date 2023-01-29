import pytz
from datetime import datetime


def get_datetime_now_cet() -> datetime:
    return datetime.now(pytz.timezone('Europe/Berlin'))


def getDateNowCet() -> datetime.time:
    datetime_now = get_datetime_now_cet()
    return datetime_now.date()
