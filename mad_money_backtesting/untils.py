import datetime

import pandas as pd


def pd_date_to_datetime(date, hour=None, minute=None):
    date = pd.to_datetime(date)
    hour = date.hour if hour is None else hour
    minute = date.minute if minute is None else minute
    return datetime.datetime(date.year, date.month, date.day, hour, minute, 0, 0)
