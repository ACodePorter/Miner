from datetime import datetime, date, timedelta


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
