from datetime import datetime

import numpy
from detonator import make_db_connection, get_logger, mongo_2_df, SingletonParent
from mongoengine import QuerySet

from .models import TickerDailyInfo, IndexTickers

_logger = get_logger('Indicators')


class Indicators(SingletonParent):
    def __init__(self):
        make_db_connection()

    def _calculate_sma(self, ticker: str, since: str | datetime = None, interval='1d', period: int = 20):
        _logger.info(f'Calculating sma for {ticker} since {since} @ interval:{interval} period:{period}')
        ticker = ticker.upper()
        query = {'ticker__iexact': ticker, 'interval__iexact': interval}
        if since:
            query['trade_date__gte'] = since if isinstance(since, datetime) else datetime.strptime(since, '%Y%m%d')
        _logger.debug(f'query:{query}')
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

    def _get_since_trade_date_for_sma(self, ticker: str, interval: str = '1d', period: int = 20) -> datetime | None:
        ticker = ticker.upper()
        query = {'ticker__iexact': ticker,
                 'interval__iexact': interval,
                 f'sma{period}__exists': True}

        infos: QuerySet = TickerDailyInfo.objects(**query)
        if infos.count() == 0:
            # 对应的均线从来没有计算过，从头开始计算，返回 None
            return None
        info: TickerDailyInfo = infos.order_by('-trade_date').first()  # latest info with sma

        query = {'ticker__iexact': ticker,
                 'interval__iexact': interval,
                 'trade_date__lte': info.trade_date}
        info = TickerDailyInfo.objects(**query).order_by('-trade_date').skip(period).first()
        if info is None:
            _logger.warning(f'Illegal state _get_since_trade_date_for_sma for {ticker}')
            return None
        _logger.debug(f'since {info.trade_date} of {ticker} for sma{period}')
        return info.trade_date

    def update_sma(self, ticker: str, interval: str = '1d', period: int = 20) -> bool:
        """
        Before calling this function, you should call update_tikers_daily_info
        """
        try:
            since = self._get_since_trade_date_for_sma(ticker, interval=interval, period=period)
            self._calculate_sma(ticker, since=since, interval=interval, period=period)
            return True
        except Exception as e:
            _logger.error(f'Failed to update_sma for {ticker}', exc_info=e)
            return False

    def update_spx_daily_sma(self) -> bool:
        try:
            make_db_connection()
            index_tickers: IndexTickers = IndexTickers.objects(index_name='spx').order_by('-as_of_date').first()
            if not index_tickers:
                _logger.error('No index tickers found for spx')
                return False
            to_update = index_tickers.tickers
            for _ in range(3):
                # retry for max 3 times
                results = {
                    ticker: all(
                        [
                            self.update_sma(ticker, interval='1d', period=20),
                            self.update_sma(ticker, interval='1d', period=50),
                            self.update_sma(ticker, interval='1d', period=200),
                        ]
                    )
                    for ticker in to_update
                }
                filtered_dict = {key: value for key, value in results.items() if not value}
                to_update = list(filtered_dict.keys())
                if not to_update:
                    return True
                else:
                    _logger.info(f'Re-Updating spx daily sma:{to_update}')
        except Exception as e:
            _logger.error('Failed to update spx sma', exc_info=e)
            return False
