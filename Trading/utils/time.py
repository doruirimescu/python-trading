import pytz
from datetime import datetime


def getDatetimeNowCet() -> datetime:
    return datetime.now(pytz.timezone('Europe/Berlin'))


def getDateNowCet() -> datetime.time:
    datetime_now = getDatetimeNowCet()
    return datetime_now.date()
