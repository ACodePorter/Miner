import os
import time
from functools import reduce
from random import random

import pandas as pd
import requests
from detonator import SingletonParent, get_logger, md5_iterable, make_db_connection
from pandas import DataFrame
from yfinance import Ticker as YTicker

from ._trade_cal import TradeCalendarShovel
from .models import IndexTickers, Ticker

_logger = get_logger('MarketDataShovel')
_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()


class MarketDataShovel(SingletonParent):
    def __init__(self):
        os.environ['HTTP_PROXY'] = 'socks5://127.0.0.1:8001'
        os.environ['HTTPS_PROXY'] = 'socks5://127.0.0.1:8001'

    def _fetch_spx_tickers(self) -> pd.DataFrame:
        url = 'https://www.slickcharts.com/sp500'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        }
        try:
            request = requests.get(url, headers=headers)
            if datas := pd.read_html(request.text):
                data = datas[0]
                data.sort_values(by=['Symbol'], ascending=True, inplace=True, ignore_index=True)
                data = data[['Company', 'Symbol']]
                data.rename({'Symbol': 'ticker', 'Company': 'name'}, axis='columns', inplace=True)
                _logger.debug(f'spx tickers:{data}')
                return data
            else:
                _logger.error(f'Failed to get data from {url}')
                return DataFrame()
        except Exception as e:
            _logger.error(f'Failed to get data from {url}', exc_info=e)
            return DataFrame()

    def update_spx_tickers(self) -> bool:
        if self._is_index_tickers_latest('spx'):
            _logger.info('spx index already latest, skip updating')
            return True
        make_db_connection()
        tickers = self._fetch_spx_tickers()
        if tickers.empty:
            _logger.error('Got Empty tickers for spx')
            return False

        def _accamulte(l: list, i) -> list:
            l.append(i)
            return l

        ticker_list = reduce(lambda x, y: _accamulte(x, y), tickers['ticker'].values, [])
        _logger.debug(f'ticker list:\n{ticker_list}')
        as_of_date = _tcs.last_us_trade_day_before_today()
        if local_latest_tickers := self.get_latest_index_tickers(
                index_name='spx'
        ):
            local_md5 = md5_iterable(local_latest_tickers.tickers)
            fetched_md5 = md5_iterable(ticker_list)
            if local_md5 and fetched_md5 and local_md5 == fetched_md5:
                _logger.info('Same local and fetched md5 for spx update, update as of date')
                local_latest_tickers.update(as_of_date=as_of_date)
                local_latest_tickers.save()
            elif fetched_md5 and not local_md5:
                _logger.info('No local md5 for spx update, save new ones')
                IndexTickers(index_name='spx', tickers=local_latest_tickers, as_of_date=as_of_date).save()
        else:
            _logger.info('No local spx index, save new ones')
            IndexTickers(index_name='spx', tickers=ticker_list, as_of_date=as_of_date).save()

    def _is_index_tickers_latest(self, index_name: str) -> bool:
        as_of_date = _tcs.last_us_trade_day_before_today()
        return IndexTickers.objects(index_name=index_name, as_of_date=as_of_date).count() > 0

    def get_latest_index_tickers_before(self, index_name: str, as_of_date: str = '',
                                        inclusive=False) -> IndexTickers:
        make_db_connection()
        as_of_date = as_of_date or _tcs.last_us_trade_day_before_today()
        queries = {
            'index_name': index_name
        }
        if inclusive:
            queries['as_of_date__lte'] = as_of_date
        else:
            queries['as_of_date__lt'] = as_of_date
        return IndexTickers.objects(__raw__=queries).order_by('-as_of_date').first()

    def get_latest_index_tickers(self, index_name: str) -> IndexTickers:
        make_db_connection()
        return IndexTickers.objects(index_name=index_name).order_by('-as_of_date').first()

    def update_ticker_info(self, ticker: str | YTicker) -> bool:
        if not isinstance(ticker, (str, YTicker)):
            _logger.error(f'update_ticker_info: invalid arg: {ticker}')
            return False
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
                    _logger.error(f'Illegal argument ticker:{ticker} typeof {type(ticker)}')
                    return False

                local_ticker: Ticker = Ticker.objects(ticker__iexact=ticker).order_by('-as_of_date').first() or Ticker(
                    ticker=ticker).save()

                def is_info_full() -> bool:
                    if local_ticker:
                        return all([local_ticker.industry, local_ticker.industryKey, local_ticker.industryDisp,
                                    local_ticker.sector, local_ticker.sectorKey, local_ticker.sectorDisp])
                    else:
                        return False

                if is_info_full():
                    _logger.info(f'Tikcer({ticker}) already full, skip')
                    return True
                info = yticker.get_info()

                local_ticker.name = info['shortName']
                local_ticker.industry = info['industry']
                local_ticker.industryKey = info['industryKey']
                local_ticker.industryDisp = info['industryDisp']
                local_ticker.sector = info['sector']
                local_ticker.sectorKey = info['sectorKey']
                local_ticker.sectorDisp = info['sectorDisp']
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

    def update_spx_tickers_info(self) -> bool:
        try:
            make_db_connection()
            if tickers := self.get_latest_index_tickers(index_name='spx'):
                results = {}
                for ticker in tickers.tickers:
                    results[ticker] = self.update_ticker_info(ticker)
                    _logger.info('sleeping ......')
                    time.sleep(random() * 20)
                _logger.info(f'update_ticker_info results:{results}')
                return all(results.values())
            else:
                return False
        except Exception as e:
            _logger.error('Failed to update spx tickers info', exc_info=e)
            return False
