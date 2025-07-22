import time
from datetime import datetime
from functools import reduce
from random import random
from typing import List, Literal
import pytz

import pandas as pd
import requests
from detonator import SingletonParent, get_logger, md5_iterable, make_db_connection, df_2_mongo, add_minus_to_YYYYmmdd, \
    tomorrow_of, datetime_from_str, mongo_2_df, sleep
from pandas import DataFrame
from yfinance import Ticker as YTicker

from ._ishares_scraper import IsharesScraper
from ._trade_cal import TradeCalendarShovel
from .models import IndexTickers, Ticker, TickerDailyInfo, regulate_ticker_daily_info
from .utils import TickerRegulator

_logger = get_logger('MarketDataShovel')
_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()


class MarketDataShovel(SingletonParent):
    """
    A class to fetch and manage market data, including index tickers and ticker information.
    TODO: move spx fetching to separate scraper
    """

    TICKER_EXCHANGE_MAP = {
        '^HSI': ('hk', 'XHKG', pytz.timezone('Asia/Hong_Kong')),
        '^SPX': ('us', 'XNYS', pytz.timezone('America/New_York')),
        '^NDX': ('us', 'XNYS', pytz.timezone('America/New_York')),
        '^RUT': ('us', 'XNYS', pytz.timezone('America/New_York')),
    }

    def __init__(self):
        self._last_yahoo_fetch_time = datetime.now()
        self._ishares_shovel: IsharesScraper = IsharesScraper.get_instance()
        self._ticker_regulator: TickerRegulator = TickerRegulator.get_instance()

    def _country_exchange_of(self, ticker: str) -> tuple[str, str, pytz.timezone]:
        if ticker in self.TICKER_EXCHANGE_MAP:
            return self.TICKER_EXCHANGE_MAP[ticker]
        else:
            return ('us', 'XNYS', pytz.timezone('America/New_York'))

    def _fetch_spx_tickers(self) -> pd.DataFrame:
        # sourcery skip: extract-method, remove-unnecessary-else
        url = 'https://www.slickcharts.com/sp500'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if datas := pd.read_html(resp.text):
                data = datas[0]
                data.sort_values(by=['Symbol'], ascending=True,
                                 inplace=True, ignore_index=True)
                data = data[['Company', 'Symbol']]
                data.rename({'Symbol': 'ticker', 'Company': 'name'},
                            axis='columns', inplace=True)
                data['ticker'] = data['ticker'].str.replace(
                    '.', '-', regex=False)
                _logger.debug('spx tickers: %s', data)
                return data
            else:
                _logger.error('Failed to get data from %s', url)
                return DataFrame()
        except Exception as e:
            _logger.error('Failed to get data from %s', url, exc_info=e)
            return DataFrame()

    def _fetch_tickers_by_idx(self, index_name: Literal['spx', 'iwd', 'iwf', 'iwm'] = 'spx') -> pd.DataFrame:
        """
        fetch component tickers by index name
        spx: S&P 500 Index
        iwd: iShares Russell 1000 Value ETF
        iwf: iShares Russell 1000 Growth ETF
        iwm: iShares Russell 2000 ETF
        """
        if index_name == 'spx':
            return self._fetch_spx_tickers()
        elif index_name in ['iwd', 'iwf', 'iwm']:
            _logger.info('Fetching %s tickers from ishares_shovel', index_name)
            return self._ishares_shovel.fetch_tickers_by_idx(index_name=index_name)
        _logger.warning(
            'Unknown index: %s, returning empty DataFrame', index_name)
        return DataFrame()

    def update_tickers_by_idx(self, idx: Literal['spx', 'iwd', 'iwf', 'iwm'] = 'spx') -> bool:
        make_db_connection()
        if self._is_index_tickers_latest(idx):
            _logger.info(f'{idx} index already latest, skip updating')
            return True
        tickers = self._fetch_tickers_by_idx(index_name=idx)
        if tickers.empty:
            _logger.error('Got Empty tickers for spx')
            return False

        def _accumulte(l: list, i) -> list:
            i = self._ticker_regulator.validate_ticker(i)
            if i:
                l.append(i.replace('-', '.'))
            return l

        ticker_list = reduce(lambda x, y: _accumulte(
            x, y), tickers['ticker'].values, [])
        _logger.info('%s ticker list:\n%s', idx, ticker_list)
        as_of_date = _tcs.last_closed_us_trade_date()
        _logger.debug('as_of_date:%s', as_of_date)
        if local_latest_tickers := self.get_latest_index_tickers(
                index_name=idx
        ):
            _logger.debug('local_latest_tickers:%s', local_latest_tickers)
            local_md5 = md5_iterable(local_latest_tickers.tickers)
            fetched_md5 = md5_iterable(ticker_list)
            _logger.debug('local_md5:%s fetched_md5:%s',
                          local_md5, fetched_md5)
            if local_md5 and fetched_md5 and local_md5 == fetched_md5:
                _logger.info(
                    'Same local and fetched md5 for spx update, update as of date')
                local_latest_tickers.update(as_of_date=as_of_date)
                local_latest_tickers.save()
                return True
        _logger.info('Save new tickers for %s', idx)
        IndexTickers(index_name=idx, tickers=ticker_list,
                     as_of_date=as_of_date).save()
        return True

    def update_spx_tickers(self) -> bool:
        return self.update_tickers_by_idx(idx='spx')

    def update_iwd_tickers(self) -> bool:
        return self.update_tickers_by_idx(idx='iwd')

    def update_iwf_tickers(self) -> bool:
        return self.update_tickers_by_idx(idx='iwf')

    def update_iwm_tickers(self) -> bool:
        return self.update_tickers_by_idx(idx='iwm')

    def _is_index_tickers_latest(self, index_name: str) -> bool:
        as_of_date = _tcs.last_closed_us_trade_date()
        return IndexTickers.objects(index_name=index_name, as_of_date=as_of_date).count() > 0

    def get_index_tickers_on(self, index_name: str, as_of_date: str = '') -> IndexTickers:
        """
        获取指定日期的指数成分股
        """
        make_db_connection()
        as_of_date = as_of_date or _tcs.last_us_trade_day_before_today()
        queries = {
            'index_name': index_name,
            'as_of_date__gte': as_of_date
        }
        _logger.debug(f'get_index_tickers_on:{queries}')
        return IndexTickers.objects(**queries).order_by('as_of_date').limit(1).first()

    def get_latest_index_tickers(self, index_name: str) -> IndexTickers:
        make_db_connection()
        return IndexTickers.objects(index_name=index_name).order_by('-as_of_date').limit(1).first()

    def update_ticker_info(self, ticker: str | YTicker) -> bool:
        if not isinstance(ticker, (str, YTicker)):
            _logger.error(f'update_ticker_info: invalid arg: {ticker}')
            return False
        _logger.info('updating ticker info: %s', ticker)
        try:
            make_db_connection()
            if ticker:
                # ensure cap ticker
                if isinstance(ticker, str):
                    ticker = ticker.upper()
                    yticker = YTicker(ticker.replace('.', '-'))
                elif isinstance(ticker, Ticker):
                    yticker = ticker
                    ticker = ticker.ticker.replace('-', '.').upper()
                else:
                    _logger.error(
                        f'Illegal argument ticker:{ticker} typeof {type(ticker)}')
                    return False

                local_ticker: Ticker = Ticker.objects(ticker=ticker).order_by('-as_of_date').limit(
                    1).first() or Ticker(
                    ticker=ticker).save()

                def is_info_full() -> bool:
                    if local_ticker:
                        return all([local_ticker.industry, local_ticker.industryKey, local_ticker.industryDisp,
                                    local_ticker.sector, local_ticker.sectorKey, local_ticker.sectorDisp])
                    else:
                        return False

                if is_info_full():
                    _logger.info('Tikcer(%s) already full, skip', ticker)
                    return True
                _logger.info('Fetching info for %s from yahoo', ticker)
                if (datetime.now() - self._last_yahoo_fetch_time).total_seconds() < 2:
                    _logger.info('sleeping ......')
                    sleep()
                self._last_yahoo_fetch_time = datetime.now()
                info = yticker.get_info()

                local_ticker.name = info['shortName'] if 'shortName' in info else 'N/A'
                local_ticker.industry = info['industry'] if 'industry' in info else 'N/A'
                local_ticker.industryKey = info['industryKey'] if 'industryKey' in info else 'N/A'
                local_ticker.industryDisp = info['industryDisp'] if 'industryDisp' in info else 'N/A'
                local_ticker.sector = info['sector'] if 'sector' in info else 'N/A'
                local_ticker.sectorKey = info['sectorKey'] if 'sectorKey' in info else 'N/A'
                local_ticker.sectorDisp = info['sectorDisp'] if 'sectorDisp' in info else 'N/A'
                local_ticker.save()
                # for k, v in info.items():
                #     _logger.debug(f'{k}:{v}')
                return True
            else:
                _logger.error('update_ticker_info failed: No ticker provided')
                return False
        except Exception as e:
            _logger.error(f'Failed to update ticker:{ticker}', exc_info=e)
            return False

    def update_hsi_daily_info(self) -> bool:
        return self.update_ticker_daily_info('^HSI')

    def update_tickers_info(self, tickers: List[str | YTicker]) -> bool:
        if tickers:
            return all([self.update_ticker_info(ticker) for ticker in tickers])
        else:
            _logger.warning('no tickers provided')
            return False

    def update_tickers_info_by_idx(self, index_name: str) -> bool:
        try:
            _logger.info(index_name)
            make_db_connection()
            if tickers := self.get_latest_index_tickers(index_name=index_name):
                results = {}
                results = {ticker: self.update_ticker_info(
                    ticker) for ticker in tickers.tickers}
                false_tickers = [k for k, v in results.items() if not v]
                _logger.info('%s results: %s',
                             index_name, ('failure: ' + ','.join(false_tickers)) if false_tickers else 'all success')
                return all(results.values())
            else:
                _logger.error('No tickers provided for %s', index_name)
                return False
        except Exception as e:
            _logger.error('Failed to update %s tickers info',
                          index_name, exc_info=e)
            return False

    def update_spx_tickers_info(self) -> bool:
        return self.update_tickers_info_by_idx('spx')

    def update_iwd_tickers_info(self) -> bool:
        return self.update_tickers_info_by_idx('iwd')

    def update_iwf_tickers_info(self) -> bool:
        return self.update_tickers_info_by_idx('iwf')

    def update_iwm_tickers_info(self) -> bool:
        return self.update_tickers_info_by_idx('iwm')

    def update_ticker_daily_info(self, ticker: str | YTicker) -> bool:
        if isinstance(ticker, str):
            ticker = ticker.upper()
            yticker: YTicker = YTicker(ticker.replace('.', '-'))
        elif isinstance(ticker, YTicker):
            yticker = ticker
            ticker = yticker.ticker.replace('-', '.')
        else:
            _logger.error(
                'Illegal argument for update_ticker_daily_info: %s', ticker)
            return False
        _logger.info(ticker)
        now = datetime.now()
        tdi = TickerDailyInfo.objects(
            ticker=ticker).order_by('-trade_date').limit(1).first()
        tdi_time = (datetime.now() - now).total_seconds()
        if tdi_time > 0.5:
            _logger.warning('Slow query %s: %s', ticker, tdi_time)
        country, exchange, _ = self._country_exchange_of(ticker)
        if trade_dates := _tcs.trade_dates_since(country=country, exchange=exchange, start_date=tdi.trade_date.strftime('%Y%m%d') if tdi else '00000000'):
            earliest_gap_trade_date = trade_dates[-1]
            _logger.info('Update ticker daily info for %s %s',
                         ticker, (datetime.now() - now).total_seconds())
            return self.fetch_ticker_daily_info_to_db(yticker=yticker, start_date=earliest_gap_trade_date,
                                                      end_date=tomorrow_of(_tcs.last_closed_trade_date(country=country, exchange=exchange)).strftime(
                                                          '%Y%m%d'))
        else:
            _logger.info(
                'No update ticker daily info for %s since %s', ticker, tdi.trade_date)
        return True

    def fetch_ticker_daily_info_to_db(self, yticker: YTicker, start_date: str = None, end_date: str = None,
                                      interval='1d',
                                      period='max') -> bool:
        """
        更新指定日期期间日线/股票基本数据
        start_date:inclusive
        end_date:inclusive
        """
        try:
            _logger.info(
                'Daily info from yfinance: %s:%s->%s %s %s', yticker.ticker, start_date, end_date, interval, period)
            start_date = add_minus_to_YYYYmmdd(
                start_date) if start_date else start_date
            end_date = add_minus_to_YYYYmmdd(
                end_date) if end_date else end_date
            if ((datetime.now() - self._last_yahoo_fetch_time).total_seconds() < 2):
                _logger.info('sleeping ......')
                sleep()
            self._last_yahoo_fetch_time = datetime.now()
            his: DataFrame = yticker.history(
                start=start_date, end=end_date, interval=interval, period=period)
            if his.empty:
                _logger.error(
                    'Failed to get history for %s from yahoo', yticker)
                return False
            his.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume',
                                'Dividends': 'dividends',
                                'Stock Splits': 'stock_splits', 'Capital Gains': 'capitalGains'}, inplace=True)
            his['trade_date'] = his.index.strftime('%Y,%m,%d,%H,%M,%S,%f')
            his['ticker'] = yticker.ticker.replace('-', '.')
            his['interval'] = interval
            make_db_connection()
            df_2_mongo(his, TickerDailyInfo)
            info = yticker.info
            regulated_info = regulate_ticker_daily_info(info)
            tdi: TickerDailyInfo = TickerDailyInfo.objects.order_by(
                '-trade_date').limit(1).first()
            tdi.update(**regulated_info)
            tdi.save()
            return True
        except Exception as e:
            _logger.error(
                'Failed _update_ticker_daily_info for %s', yticker.ticker, exc_info=e)
            return False

    def update_tickers_daily_info_by_idx(self, index_name: str = 'spx') -> bool:
        try:
            make_db_connection()
            if not (tickers := self.get_latest_index_tickers(index_name=index_name)):
                return False
            _logger.debug('full: %s', tickers.tickers)
            to_update = list(tickers.tickers)
            for i in range(6):
                _logger.info(
                    'update_tickers_daily_info_by_idx:%s->%s:%s', index_name, i, to_update)
                to_update = self.update_tickers_daily_info(to_update)
                if not to_update:
                    return True
                else:
                    _logger.warning(
                        'Re-Update failed %s tickers: %s', index_name, to_update)
            _logger.error(
                'Failed to update %s tickers info after 6 attempts: ', index_name)
            return False
        except Exception as e:
            _logger.error('Failed to update %s tickers info',
                          index_name, exc_info=e)
            return False

    def update_spx_tickers_daily_info(self) -> bool:
        return self.update_tickers_daily_info_by_idx('spx')

    def update_iwd_tickers_daily_info(self) -> bool:
        return self.update_tickers_daily_info_by_idx('iwd')

    def update_iwf_tickers_daily_info(self) -> bool:
        return self.update_tickers_daily_info_by_idx('iwf')

    def update_iwm_tickers_daily_info(self) -> bool:
        return self.update_tickers_daily_info_by_idx('iwm')

    def update_tickers_daily_info(self, tickers: List[str]) -> List[str]:
        _logger.debug('tickers:%s', tickers)
        try:
            make_db_connection()
            if tickers:
                results = {}
                for ticker in tickers:
                    now = datetime.now()
                    results[ticker] = self.update_ticker_daily_info(ticker)
                    _logger.info('%s loop time for %s', ticker,
                                 (datetime.now() - now).total_seconds())
                filtered_dict = {key: value for key,
                                 value in results.items() if not value}
                return list(filtered_dict.keys())

            else:
                _logger.error('Illegal argument %s', tickers)
                return tickers
        except Exception as e:
            _logger.error(
                'Failed to update daily info for %s', tickers, exc_info=e)
            return tickers

    def get_tickers_daily_info_on(self, tickers: str | List[str], trade_date: str | datetime,
                                  interval: str = '1d') -> DataFrame:
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(trade_date, str):
            trade_date = datetime_from_str(trade_date)
        if not trade_date:
            _logger.error('Illegal trade_date: %s', trade_date)
            return pd.DataFrame()
        return mongo_2_df(TickerDailyInfo.objects(ticker__in=tickers, trade_date=trade_date, interval=interval))

    def get_ticker_daily_info(self, ticker: str, start_date: str | datetime, end_date: str | datetime, interval: str = '1d') -> DataFrame:
        ticker = ticker.replace('-', '.').upper()
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(
                    start_date, '%Y,%m,%d,%H,%M,%S,%f')
            except Exception as e:
                start_date = datetime.strptime(start_date, '%Y%m%d')
        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, '%Y,%m,%d,%H,%M,%S,%f')
            except Exception as e:
                end_date = datetime.strptime(end_date, '%Y%m%d')
        return mongo_2_df(TickerDailyInfo.objects(ticker=ticker, trade_date__gte=start_date, trade_date__lte=end_date, interval=interval).order_by('trade_date'))
