from detonator import SingletonParent, get_logger

from .models import Ticker

_logger = get_logger('TickerManager')


class TickerManager(SingletonParent):
    def get_latest_as_of_date_before(self, as_of_date: str = '30001231', inclusive=False) -> str:
        if (
                as_of_dates := Ticker.objects()
            .only('as_of_date')
            .order_by('-as_of_date')
            .distinct(field='as_of_date')
        ):
            _logger.debug(f'as_of_dates: {as_of_dates}')
            as_of_dates = sorted(as_of_dates, reverse=True)
            for d in as_of_dates:
                if (
                        not inclusive
                        and d < as_of_date
                        or
                        inclusive
                        and d <= as_of_date
                ):
                    return d
        return ''
