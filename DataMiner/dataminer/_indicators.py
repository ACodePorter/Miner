from datetime import datetime

import os
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor

import numpy
from detonator import is_in_daemon, make_db_connection, get_logger, mongo_2_df, SingletonParent
from mongoengine import QuerySet

from .models import TickerDailyInfo, IndexTickers

_logger = get_logger('Indicators')


def _get_since_trade_date_for_sma(ticker: str, interval: str = '1d', period: int = 20) -> datetime | None:
    ticker = ticker.upper()
    query = {'ticker__iexact': ticker,
             'interval__iexact': interval,
             f'sma{period}__exists': True}

    infos: QuerySet = TickerDailyInfo.objects(**query)
    if infos.count() == 0:
        # 对应的均线从来没有计算过，从头开始计算，返回 None
        return None
    info: TickerDailyInfo = infos.order_by(
        '-trade_date').first()  # latest info with sma

    query = {'ticker__iexact': ticker,
             'interval__iexact': interval,
             'trade_date__lte': info.trade_date}
    info = TickerDailyInfo.objects(
        **query).order_by('-trade_date').skip(period).first()
    if info is None:
        _logger.warning(
            'Illegal state _get_since_trade_date_for_sma for %s', ticker)
        return None
    _logger.debug('since %s of %s for sma%d', info.trade_date, ticker, period)
    return info.trade_date


def _calculate_sma(ticker: str, since: str | datetime = None, interval='1d', period: int = 20):
    _logger.info(
        'Calculating sma for %s since %s @ interval:%s period:%d', ticker, since, interval, period)
    ticker = ticker.upper()
    query = {'ticker__iexact': ticker, 'interval__iexact': interval}
    if since:
        query['trade_date__gte'] = since if isinstance(
            since, datetime) else datetime.strptime(since, '%Y%m%d')
    _logger.debug('query:%s', query)
    tickers = TickerDailyInfo.objects(**query).order_by('trade_date')
    tickers_df = mongo_2_df(tickers)
    # _logger.debug(tickers_df)
    sma = tickers_df['close'].rolling(window=period).mean()
    for i, t in enumerate(tickers):
        # TODO: 优化这里的循环，使用正确的数据顺序+dropna 代替现在的完整遍历
        if not numpy.isnan(sma[i]):
            xp = f't.sma{period} = {sma[i]}'
            exec(xp)
            t.save()
        # else:
        #     _logger.warning(f'Skip nan: {t.ticker} @{t.trade_date}')


def _update_sma_with_details(ticker: str, interval: str = '1d', period: int = 20) -> bool:
    """
    Before calling this function, you should call update_tikers_daily_info
    """
    _logger.info('Updating sma for %s @ interval:%s period:%d',
                 ticker, interval, period)
    try:
        since = _get_since_trade_date_for_sma(
            ticker, interval=interval, period=period)
        _calculate_sma(ticker, since=since,
                       interval=interval, period=period)
        return True
    except Exception as e:
        _logger.error('Failed to update_sma for %s', ticker, exc_info=e)
        return False


def _update_sma_for_ticker(ticker: str) -> bool:
    _logger.info('Updating sma for %s', ticker)
    make_db_connection()
    result = all(
        [
            _update_sma_with_details(ticker, interval='1d', period=20),
            _update_sma_with_details(ticker, interval='1d', period=50),
            _update_sma_with_details(ticker, interval='1d', period=200),
        ]
    )
    _logger.info('Updated sma for %s:%s', ticker, result)
    return {ticker: result}


def update_spx_daily_sma() -> bool:
    try:
        make_db_connection()
        index_tickers: IndexTickers = IndexTickers.objects(
            index_name='spx').order_by('-as_of_date').first()
        if not index_tickers:
            _logger.error('No index tickers found for spx')
            return False
        to_update = index_tickers.tickers
        for i in range(3):
            # retry for max 3 times
            _logger.info('Updating spx daily sma: %d -> %s', i, to_update)
            temp_results: list = None
            if is_in_daemon():
                _logger.info('Using ThreadPoolExecutor')
                with ThreadPoolExecutor() as executor:
                    temp_results = list(executor.map(
                        _update_sma_for_ticker, to_update))
            else:
                _logger.info('Using Process Pool')
                with Pool(processes=os.cpu_count()) as p:
                    temp_results: list = p.map(
                        _update_sma_for_ticker, to_update)
            results = {}
            for r in temp_results:
                results.update(r)
            filtered_dict = {key: value for key,
                             value in results.items() if not value}
            to_update = list(filtered_dict.keys())
            if not to_update:
                return True
            else:
                _logger.info('Re-Updating spx daily sma: %s', to_update)
    except Exception as e:
        _logger.error('Failed to update spx sma', exc_info=e)
        return False


class Indicators(SingletonParent):
    def __init__(self):
        make_db_connection()

    def update_spx_daily_sma(self) -> bool:
        return update_spx_daily_sma()
