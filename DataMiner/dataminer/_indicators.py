"""
TODO:
    - make it a singleton class
    - improve db query performance
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from multiprocessing import Pool
from typing import Literal, Dict

import numpy
from detonator import is_in_daemon, make_db_connection, get_logger, mongo_2_df, SingletonParent
from mongoengine import QuerySet
from pymongo import UpdateOne

from .models import TickerDailyInfo, IndexTickers

_logger = get_logger('Indicators')


def _get_since_trade_date_for_indicator(ticker: str, indicator: Literal['sma', 'ema'] = 'sma', interval: str = '1d',
                                        period: int = 20) -> datetime | None:
    """
    Generic function to get the since trade date for any indicator.
    """
    ticker = ticker.upper()
    # First get the most recent document with the indicator
    query = {
        'ticker': ticker,
        'interval': interval
    }
    # Use MongoEngine's proper syntax for existence checks
    query[f'{indicator}{period}__exists'] = True
    query[f'{indicator}{period}__ne'] = None

    # Use the compound index for efficient querying
    infos: QuerySet = TickerDailyInfo.objects(
        **query).order_by('-trade_date').limit(1)
    if infos.count() == 0:
        return None
    info: TickerDailyInfo = infos.first()

    # Then get the document that is 'period' days before
    query = {
        'ticker': ticker,
        'interval': interval,
        'trade_date__lte': info.trade_date
    }
    info = TickerDailyInfo.objects(
        **query).order_by('-trade_date').skip(period).first()
    if info is None:
        _logger.warning(
            'Illegal state _get_since_trade_date_for_indicator for %s (%s)', ticker, indicator)
        return None
    _logger.debug('since %s of %s for %s%d',
                  info.trade_date, ticker, indicator, period)
    return info.trade_date


def _calculate_indicator(ticker: str, indicator: Literal['sma', 'ema'] = 'sma', since: str | datetime = None,
                         interval: str = '1d', period: int = 20):
    _logger.info(
        'Calculating %s for %s since %s @ interval:%s period:%d', indicator, ticker, since, interval, period)
    ticker = ticker.upper()
    query = {'ticker': ticker, 'interval': interval}
    if since:
        query['trade_date__gte'] = since if isinstance(
            since, datetime) else datetime.strptime(since, '%Y%m%d')
    _logger.debug('query:%s', query)
    tickers = TickerDailyInfo.objects(**query).order_by('trade_date')
    tickers_df = mongo_2_df(tickers)
    _logger.info('Found %d documents for %s', len(tickers_df), ticker)

    if indicator == 'sma':
        values = tickers_df['close'].rolling(window=period).mean()
    elif indicator == 'ema':
        values = tickers_df['close'].ewm(span=period, adjust=False).mean()
    else:
        raise ValueError(f'Unsupported indicator: {indicator}')

    # Create a dictionary mapping trade dates to indicator values
    updates = {}
    for i, t in enumerate(tickers):
        if not numpy.isnan(values[i]):
            updates[t.trade_date] = float(values[i])

    _logger.info('Calculated %d valid indicator values for %s',
                 len(updates), ticker)
    if len(updates) > 0:
        _logger.info('Sample values: %s', dict(list(updates.items())[:3]))

    if updates:
        _logger.info('Updating %d documents for %s %s%d',
                     len(updates), ticker, indicator, period)
        start_time = datetime.now()

        # Create bulk operations
        bulk_operations = []
        for trade_date, value in updates.items():
            # Create update operation without checking current value
            bulk_operations.append(
                UpdateOne(
                    {'ticker': ticker, 'interval': interval, 'trade_date': trade_date.strftime(
                        '%Y,%m,%d,%H,%M,%S,000000')},
                    {'$set': {f'{indicator}{period}': value}}
                )
            )

        if bulk_operations:
            _logger.info('Executing %d bulk operations for %s',
                         len(bulk_operations), ticker)
            # Log first few operations for debugging
            for i, op in enumerate(bulk_operations[:3]):
                filter_doc = {'ticker': ticker, 'interval': interval, 'trade_date': list(
                    updates.keys())[i].strftime('%Y,%m,%d,%H,%M,%S,000000')}
                update_doc = {
                    '$set': {f'{indicator}{period}': list(updates.values())[i]}}
                _logger.debug('Sample operation %d: %s', i, {
                    'filter': filter_doc,
                    'update': update_doc
                })

            result = TickerDailyInfo._get_collection().bulk_write(
                bulk_operations, ordered=False)
            duration = (datetime.now() - start_time).total_seconds()
            _logger.info('Update completed in %.2f seconds. Modified: %d, Matched: %d',
                         duration, result.modified_count, result.matched_count)
    else:
        _logger.info('No updates for %s %s%d', ticker, indicator, period)


def _update_indicator_with_details(ticker: str, indicator: Literal['sma', 'ema'] = 'sma', interval: str = '1d',
                                   period: int = 20) -> bool:
    """
    Before calling this function, you should call update_tikers_daily_info.
    Updates the specified indicator for the given ticker.
    """
    _logger.info('Updating %s for %s @ interval:%s period:%d',
                 indicator, ticker, interval, period)
    try:
        since = _get_since_trade_date_for_indicator(
            ticker, indicator=indicator, interval=interval, period=period)
        _calculate_indicator(
            ticker, indicator=indicator, since=since,
            interval=interval, period=period)
        return True
    except Exception as e:
        _logger.error('Failed to update %s for %s',
                      indicator, ticker, exc_info=e)
        return False


def _update_ma_for_ticker(ticker: str) -> Dict[str, bool]:
    _logger.info('Updating sma for %s', ticker)
    make_db_connection()
    result = all(
        [
            _update_indicator_with_details(
                ticker, indicator='ema', interval='1d', period=10),
            _update_indicator_with_details(
                ticker, indicator='ema', interval='1d', period=20),
            _update_indicator_with_details(
                ticker, indicator='sma', interval='1d', period=10),
            _update_indicator_with_details(
                ticker, indicator='sma', interval='1d', period=20),
            _update_indicator_with_details(
                ticker, indicator='sma', interval='1d', period=50),
            _update_indicator_with_details(
                ticker, indicator='sma', interval='1d', period=200),
        ]
    )
    _logger.info('Updated sma for %s:%s', ticker, result)
    return {ticker: result}


def update_daily_ma_by_idx(index_name: str) -> bool:
    try:
        make_db_connection()
        index_tickers: IndexTickers = IndexTickers.objects(
            index_name=index_name).order_by('-as_of_date').limit(1).first()
        if not index_tickers:
            _logger.error('No index tickers found for %s', index_name)
            return False
        to_update = index_tickers.tickers
        for i in range(3):
            # retry for max 3 times
            _logger.info('Updating %s daily ma: %d -> %s',
                         index_name, i, to_update)
            temp_results: list = None
            if is_in_daemon():
                _logger.info('Using ThreadPoolExecutor')
                with ThreadPoolExecutor() as executor:
                    temp_results = list(executor.map(
                        _update_ma_for_ticker, to_update))
            else:
                _logger.info('Using Process Pool')
                with Pool(processes=os.cpu_count()) as p:
                    temp_results: list = p.map(
                        _update_ma_for_ticker, to_update)
            results = {}
            for r in temp_results:
                results.update(r)
            filtered_dict = {key: value for key,
                             value in results.items() if not value}
            to_update = list(filtered_dict.keys())
            if not to_update:
                return True
            else:
                _logger.info('Re-Updating %s daily ma: %s',
                             index_name, to_update)
        return False
    except Exception as e:
        _logger.error('Failed to update %s ma', index_name, exc_info=e)
        return False


class Indicators(SingletonParent):
    def __init__(self):
        make_db_connection()

    def update_spx_daily_ma(self) -> bool:
        return update_daily_ma_by_idx('spx')

    def update_daily_ma_by_idx(self, index_name: str) -> bool:
        return update_daily_ma_by_idx(index_name)

    def update_indicators_for_tickers(self, tickers: list[str]) -> bool:
        """
        Update indicators for the given list of tickers.
        :param tickers: List of ticker symbols.
        :return: Dictionary with ticker as key and update status as value.
        """
        results = {}
        for ticker in tickers:
            results[ticker] = _update_ma_for_ticker(ticker)
        return all(results.values())
