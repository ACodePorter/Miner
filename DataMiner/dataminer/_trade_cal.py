import datetime
from typing import List
import time

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
            end_date = datetime.datetime.now(
                pytz.timezone('America/New_York')).strftime('%Y%m%d')
            args = {
                'end_date': end_date
            }
            if (
                    latest_cal_date := TradeCalendar.objects(country='us')
                .order_by('-cal_date')
                .only('cal_date')
                .first()
            ):
                args['start_date'] = (
                    datetime.datetime.strptime(latest_cal_date.cal_date, '%Y%m%d') + datetime.timedelta(
                        days=1)).strftime(
                    '%Y%m%d')
                if args['start_date'] > args['end_date']:
                    return
                cal_df = ts.pro_api().us_tradecal(**args)
                cal_df['country'] = 'us'
                df_2_mongo(cal_df, TradeCalendar)
            else:
                self.update_historical_us_trade_calendar(start_date="19620101", end_date=end_date)
        except Exception as e:
            _logger.error(f'update_us_trade_calendar failed: {e}')

    def is_today_us_trade_day(self) -> bool:
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            today_date = datetime.datetime.now(
                pytz.timezone('America/New_York')).strftime('%Y%m%d')
            return TradeCalendar.objects(country='us', cal_date=today_date).first().is_open == True
        except Exception as e:
            _logger.error(f'is_today_us_trade_day failed: {e}')
            raise

    def last_us_trade_day_before_today(self) -> str:
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            today_date = datetime.datetime.now(
                pytz.timezone('America/New_York')).strftime('%Y%m%d')
            return TradeCalendar.objects(country='us', cal_date__lt=today_date, is_open=True).order_by('-cal_date') .first().cal_date
        except Exception as e:
            _logger.error(
                f'last_trade_day_before_today failed:{e}', stack_info=True)

    def us_trade_dates_since(self, start_date: str | datetime.date | datetime.datetime,
                             end_date: str | datetime.date | datetime.datetime = '') -> List[str] | None:
        if not isinstance(start_date, (str, datetime.date, datetime.datetime)):
            _logger.error(f'Illegal argument trade_date_since: {start_date}')
            return None
        start_date = start_date if isinstance(
            start_date, str) else start_date.strftime('%Y%m%d')
        make_db_connection()
        if not end_date:
            end_date = self.last_closed_us_trade_date()
        end_date = end_date if isinstance(
            end_date, str) else end_date.strftime('%Y%m%d')
        try:
            self.update_us_trade_calendar()
            trade_dates = TradeCalendar.objects(cal_date__gt=start_date,
                                                cal_date__lte=end_date, country='us',
                                                is_open=True).order_by('-cal_date')
            return [t.cal_date for t in trade_dates]
        except Exception as e:
            _logger.error(
                f'Failed to us_trade_dates_since:{start_date} -> {end_date}', exc_info=e)
            return None

    def last_closed_us_trade_date(self) -> str | None:
        """
        返回最近的已经收盘的交易日 YYYYmmdd
        """
        try:
            make_db_connection()
            self.update_us_trade_calendar()
            today_date = datetime.datetime.now(
                pytz.timezone('America/New_York'))
            this_cal_date: TradeCalendar = TradeCalendar.objects(country='us',
                                                                 cal_date=today_date.strftime('%Y%m%d')).first()
            if this_cal_date.is_open and today_date.hour >= 16:
                return this_cal_date.cal_date
            return self.last_us_trade_day_before_today()
        except Exception as e:
            _logger.error(
                'Failed to get last_closed_us_trade_date', exc_info=e)
            return None

    def update_historical_us_trade_calendar(self, start_date: str = '19620101', end_date: str = '20250712') -> bool:
        """
        Update US trading calendar with historical data from 1962-01-01 to 2008-10-11.
        This function fetches historical trading calendar data and stores it in the database.
        Optimized to handle large date ranges by fetching data in chunks of 6000 records.

        Args:
            start_date: Start date in YYYYMMDD format (default: '19620101')
            end_date: End date in YYYYMMDD format (default: '20081011')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            make_db_connection()
            _logger.info(
                f'Updating historical US trade calendar from {start_date} to {end_date}')

            # Convert dates to datetime for easier manipulation
            start_dt = datetime.datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.datetime.strptime(end_date, '%Y%m%d')

            # Calculate total days and estimate chunks needed
            total_days = (end_dt - start_dt).days + 1
            records_per_chunk = 6000  # Tushare can handle 6000 records per request
            # Approximate days per chunk (trading days are ~252/year)
            days_per_chunk = records_per_chunk

            _logger.info(
                f'Total date range: {total_days} days, estimated chunks: {total_days // days_per_chunk + 1}')

            current_start_dt = start_dt
            total_records_fetched = 0

            while current_start_dt <= end_dt:
                time.sleep(65)
                # Calculate end date for this chunk
                current_end_dt = min(
                    current_start_dt + datetime.timedelta(days=days_per_chunk), end_dt)

                # Convert to string format
                chunk_start = current_start_dt.strftime('%Y%m%d')
                chunk_end = current_end_dt.strftime('%Y%m%d')

                _logger.info(f'Fetching chunk: {chunk_start} to {chunk_end}')

                # Check if we already have data for this chunk
                existing_data = TradeCalendar.objects(
                    country='us',
                    cal_date__gte=chunk_start,
                    cal_date__lte=chunk_end
                ).count()

                chunk_days = (current_end_dt - current_start_dt).days + 1
                if existing_data > 0:
                    _logger.info(
                        f'Found {existing_data} existing records for chunk {chunk_start} to {chunk_end}')
                    # If we have most of the data for this chunk, skip it
                    if existing_data >= chunk_days * 0.8:  # Allow 20% tolerance for weekends/holidays
                        _logger.info(
                            f'Skipping chunk {chunk_start} to {chunk_end} - data appears complete')
                        current_start_dt = current_end_dt + \
                            datetime.timedelta(days=1)
                        continue

                # Fetch data for this chunk
                args = {
                    'start_date': chunk_start,
                    'end_date': chunk_end
                }

                try:
                    cal_df = ts.pro_api().us_tradecal(**args)

                    if cal_df is None or cal_df.empty:
                        _logger.warning(
                            f'No data received for chunk {chunk_start} to {chunk_end}')
                        current_start_dt = current_end_dt + \
                            datetime.timedelta(days=1)
                        continue

                    # Add country field
                    cal_df['country'] = 'us'

                    # Save to database
                    df_2_mongo(cal_df, TradeCalendar)

                    chunk_records = len(cal_df)
                    total_records_fetched += chunk_records
                    _logger.info(
                        f'Successfully saved {chunk_records} records for chunk {chunk_start} to {chunk_end}')

                except Exception as chunk_error:
                    _logger.error(
                        f'Failed to fetch chunk {chunk_start} to {chunk_end}: {chunk_error}')
                    # Continue with next chunk instead of failing completely

                # Move to next chunk
                current_start_dt = current_end_dt + datetime.timedelta(days=1)

            _logger.info(
                f'Historical trade calendar update completed. Total records fetched: {total_records_fetched}')
            return True

        except Exception as e:
            _logger.error(
                f'Failed to update historical US trade calendar: {e}', exc_info=True)
            return False
