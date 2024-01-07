import datetime
from typing import List

import pytz
import tushare as ts
from detonator import SingletonParent, get_logger, df_2_mongo, make_db_connection

from .models import TradeCalendar

_logger = get_logger('TradeCalendarShovel')


class TradeCalendarShovel(SingletonParent):
    """
    TODO: use another stable trade calendar data source, cause tushare is not always correct.
    """

    def update_us_trade_calendar(self):
        try:
            make_db_connection()
            end_date = datetime.datetime.now(pytz.timezone('America/New_York')).strftime('%Y%m%d')
            args = {
                'end_date': end_date
            }
            if (
                    latest_cal_date := TradeCalendar.objects(country='us')
                            .order_by('-cal_date')
                            .only('cal_date')
                            .first()
            ):
                _logger.debug(f'latest_cal_date: {latest_cal_date.cal_date}')
                args['start_date'] = (
                        datetime.datetime.strptime(latest_cal_date.cal_date, '%Y%m%d') + datetime.timedelta(
                    days=1)).strftime(
                    '%Y%m%d')
                _logger.debug(f'update_us_trade_calendar args: {args}')
                if args['start_date'] > args['end_date']:
                    _logger.info(f'skip update_us_trade_calendar: {args}')
                    return
            _logger.debug(f'update_us_trade_calendar: {args}')
            cal_df = ts.pro_api().us_tradecal(**args)
            cal_df['country'] = 'us'
            _logger.debug(f'update_us_trade_calendar: {cal_df}')
            df_2_mongo(cal_df, TradeCalendar)
        except Exception as e:
            _logger.error(f'update_us_trade_calendar failed: {e}')

    def is_today_us_trade_day(self) -> bool:
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            today_date = datetime.datetime.now(pytz.timezone('America/New_York')).strftime('%Y%m%d')
            _logger.debug(f'today_date: {today_date}')
            return TradeCalendar.objects(country='us', cal_date=today_date).first().is_open == True
        except Exception as e:
            _logger.error(f'is_today_us_trade_day failed: {e}')
            raise

    def last_us_trade_day_before_today(self) -> str:
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            today_date = datetime.datetime.now(pytz.timezone('America/New_York')).strftime('%Y%m%d')
            _logger.debug(f'today_date: {today_date}')
            return TradeCalendar.objects(country='us', cal_date=today_date).first().pretrade_date
        except Exception as e:
            _logger.error(f'last_trade_day_before_today failed:{e}', stack_info=True)

    def us_trade_dates_since(self, start_date: str | datetime.date | datetime.datetime,
                             end_date: str | datetime.date | datetime.datetime = '') -> List[str] | None:
        if not isinstance(start_date, (str, datetime.date, datetime.datetime)):
            _logger.error(f'Illegal argument trade_date_since: {start_date}')
            return None
        start_date = start_date if isinstance(start_date, str) else start_date.strftime('%Y%m%d')
        if not end_date:
            end_date = self.last_us_trade_day_before_today()
        end_date = end_date if isinstance(end_date, str) else end_date.strftime('%Y%m%d')
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            trade_dates = TradeCalendar.objects(cal_date__gt=start_date,
                                                cal_date__lte=end_date, country='us',
                                                is_open=True).order_by('-cal_date')
            return [t.cal_date for t in trade_dates]
        except Exception as e:
            _logger.error(f'Failed to us_trade_dates_since:{start_date}', exc_info=e)
            return None
