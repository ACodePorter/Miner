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

from .models import TickerDailyInfo, IndexTickers

_logger = get_logger('Indicators')


def _get_since_trade_date_for_indicator(ticker: str, indicator: Literal['sma', 'ema'] = 'sma', interval: str = '1d',
                                        period: int = 20) -> datetime | None:
    """
    Generic function to get the since trade date for any indicator.
    """
    ticker = ticker.upper()
    query = {
        'ticker': ticker,
        'interval': interval,
        f'{indicator}{period}__exists': True
    }

    infos: QuerySet = TickerDailyInfo.objects(**query).order_by('-trade_date').limit(1)
    if infos.count() == 0:
        return None
    info: TickerDailyInfo = infos.first()

    query = {
        'ticker': ticker,
        'interval': interval,
        'trade_date__lte': info.trade_date
    }
    info = TickerDailyInfo.objects(**query).order_by('-trade_date').skip(period).first()
    if info is None:
        _logger.warning(
            'Illegal state _get_since_trade_date_for_indicator for %s (%s)', ticker, indicator)
        return None
    _logger.debug('since %s of %s for %s%d', info.trade_date, ticker, indicator, period)
    return info.trade_date


def _calculate_indicator(ticker: str, indicator: Literal['sma', 'ema'] = 'sma', since: str | datetime = None,
                         interval: str = '1d', period: int = 20):
    _logger.info(
        'Calculating %s for %s since %s @ interval:%s period:%d', indicator, ticker, since, interval, period)
    ticker = ticker.upper()
    query = {'ticker__iexact': ticker, 'interval__iexact': interval}
    if since:
        query['trade_date__gte'] = since if isinstance(
            since, datetime) else datetime.strptime(since, '%Y%m%d')
    _logger.debug('query:%s', query)
    tickers = TickerDailyInfo.objects(**query).order_by('trade_date')
    tickers_df = mongo_2_df(tickers)

    if indicator == 'sma':
        values = tickers_df['close'].rolling(window=period).mean()
    elif indicator == 'ema':
        values = tickers_df['close'].ewm(span=period, adjust=False).mean()
    else:
        raise ValueError(f'Unsupported indicator: {indicator}')

    for i, t in enumerate(tickers):
        if not numpy.isnan(values[i]):
            setattr(t, f'{indicator}{period}', values[i])
            t.save()


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
        _logger.error('Failed to update %s for %s', indicator, ticker, exc_info=e)
        return False


def _update_ma_for_ticker(ticker: str) -> Dict[str, bool]:
    _logger.info('Updating sma for %s', ticker)
    make_db_connection()
    result = all(
        [
            _update_indicator_with_details(ticker, indicator='ema', interval='1d', period=10),
            _update_indicator_with_details(ticker, indicator='ema', interval='1d', period=20),
            _update_indicator_with_details(ticker, indicator='sma', interval='1d', period=10),
            _update_indicator_with_details(ticker, indicator='sma', interval='1d', period=20),
            _update_indicator_with_details(ticker, indicator='sma', interval='1d', period=50),
            _update_indicator_with_details(ticker, indicator='sma', interval='1d', period=200),
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
            _logger.info('Updating %s daily ma: %d -> %s', index_name, i, to_update)
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
                _logger.info('Re-Updating %s daily ma: %s', index_name, to_update)
        return False
    except Exception as e:
        _logger.error('Failed to update %s ma', index_name, exc_info=e)
        return False


class Indicators(SingletonParent):
    def __init__(self):
        make_db_connection()

    def update_spx_daily_sma(self) -> bool:
        return update_daily_ma_by_idx('spx')

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
