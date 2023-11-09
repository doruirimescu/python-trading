from typing import List, Dict, Optional
from datetime import date


def hist_time_of_day(highs: List[float], dates: List[date]):
    weekday_highs = dict()
    for i, date in enumerate(dates):
        weekday = date.weekday()
        if weekday not in weekday_highs:
            weekday_highs[weekday] = []
        weekday_highs[weekday].append(highs[i])

    for weekday in weekday_highs:
        weekday_highs[weekday] = sum(weekday_highs[weekday]) / len(weekday_highs[weekday])
    print(weekday_highs)
    return weekday_highs

# plot weekday_highs
