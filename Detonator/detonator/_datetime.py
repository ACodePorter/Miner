from datetime import date, datetime, timedelta

import pytz
from pytz import BaseTzInfo


def datetime_from_str(day: str) -> datetime | None:
    if str:
        try:
            return datetime.strptime(day, "%Y-%m-%d" if '-' in day else '%Y%m%d')
        except Exception as e:
            return None


def tomorrow_of(day: str | datetime | date = None) -> datetime:
    if not day:
        return datetime.now() + timedelta(days=1)
    if isinstance(day, str):
        day = datetime_from_str(day)
    tomorrow = day + timedelta(days=1)
    return tomorrow if isinstance(tomorrow, datetime) else datetime.strptime(tomorrow.strftime('%Y%m%d'), '%Y%m%d')


def utc_to_target_tz(dt: datetime, target_tz: str | BaseTzInfo) -> datetime:
    dt_utc = dt.replace(tzinfo=pytz.UTC)
    target_tz = pytz.timezone(target_tz) if isinstance(
        target_tz, str) else target_tz
    return dt_utc.astimezone(target_tz)
