import hashlib
from functools import reduce

import requests
from detonator import get_logger, df_2_mongo, SingletonParent, make_db_connection
from mongoengine import QuerySet
from pandas import DataFrame

from ._ticker_manager import TickerManager
from ._trade_cal import TradeCalendarShovel
from .models import Ticker

_logger = get_logger('IsharesShovel')

_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
_tm: TickerManager = TickerManager.get_instance()


class IsharesShovel(SingletonParent):
    """
    从 Ishare 网站抓取指数成分
    """

    def __init__(self):
        self._cookies = {
            'ts-us-ishares-locale': 'en_US',
            'StatisticalAnalyticsEnabled': 'true',
            'AllowAnalytics': 'false',
            'us-ishares-recent-funds': '239707+239710',
            'SSESSIONID_blk-one01': 'ZjRlNTRkZWUtMzA4Ny00OTc1LWFlOGUtNTc5MzU2MGNkMGEx',
            'STICKY_SESSION_COOKIE_BLK_ONE01_LIVE': '"88cadf42bce03e16"',
            'bm_mi': '6D8D5073FD8BA221DED0401FCD5E3809~YAAQrfTVF9pQe5iMAQAAXRuWphbVJfRaLGIsmQHybsO+nsIGrcnkGMISN55az8sODuFLd8iY0Mso8UbDkSG985h8zkT2TfUzZqvVBqohCbiCiuhGvwPAJv3p9qW9QpdyY3kqTvFgh3wSvKCtMrJDyWCFPBv7L7iyQsOGpjE4E42JB7iXNYa0DRlrv36qeXM20ekvYBtUSGLbVrK96h0xRXXueG0aFVeGOE7JXB3jVaSUZwLpyl37YAUk8YzLin8bdxQ65SJ41tqnMnj+EAQk+oHajj2M+YBmDhy/jx4QIY/RCnII69bGRtsfrJsOSfE/E4PJv3A7PMTTlZYq1cxAR9D91gk/nDrJhbViXzi43Ugi8Bch/qqv7RDJyNhGBSkqiA0+gazU6hYd8w4D~1',
            'ak_bmsc': 'AB47D4A2B22A38E560377BEC459E5D9D~000000000000000000000000000000~YAAQrfTVFw9Re5iMAQAAyh+WphZVQOewKWV3auDevgyCh2jgol5UT6Bj52W2swdP3tV/Pc15D/29orV3+PFCSkrdzEMXme6nYzi0cPUVKKdFvoSYBXQkluEOgn18YLC/GT5VP8u35eNALh+aGPefcla47uQCPO5mufXdPZ0vJ3ZZcd3vVv2DUTEIRCgytbwlPTUmHnieV7sE0EFfGXoQTryPB0hsDDmn3kkssEX3JGAztAPACDSuUveMu9VZkJwo31QKaxwPA5LUsjusDwM9IglJVTfkFgw/ph7GVQaB6hi8YDP1VKKEPW6ONHXoO9FMxhx9MzqwIyXH6jw6KLcf2M9cMT4GPuZONOHD5Y5S6a+UheVLGe289H321EfEnBmkVcdwSBZVCKOJ6Wp4CiruJdJ4QLgNU66SpXnuxXd63jkp0rVg1px4DsxxRfMzNhx0OhV8phzj71vN29BgJac9Z77in7tL+GScVBss+iMGsN21TPzpmUDRYFB1sbWExOX1uBU9mdyWL2pOe4OwKUxO0tNiVRYwchEo5cCgtEDZgXbJ7+jwjNhAOBClTsDgF+6ZmhLHAebATNL0726peYN6CXtebA==',
            'utag_main': 'v_id:018c4d6e352500af232d1b0a9d5005075004306d0093c$_sn:7$_se:1$_ss:1$_st:1703603705818$ses_id:1703601905818%3Bexp-session$_pn:1%3Bexp-session',
            'bm_sv': 'AC9922F958DD482771F4B1DA61DE4656~YAAQrfTVF7tTe5iMAQAA8lqWphYp5aa2G0ARJ1VLvaHFxezT+Ulr9MW6cJFW0tjEqMkpvDRg9Pq2I2jKGkPpL9aUaYzhucWo3en/Y1ZOIVQLgtuusv7S2LXD3OuDHn43R8AnS0Hi3pm6msSXgBPwyMbirb8fC7YI9Hk4iJB6UmUI+P5v37N5isSJZI7Xk4OvEUfNGXpsh0D0PNDyY6Q6B/fWSWq14/K2n0hXbnlJx80IvcyCHJjKDP90EjHjfFJFQA==~1',
        }

        self._headers = {
            'authority': 'www.ishares.com',
            'accept': '*/*',
            'accept-language': 'en-US,en-CA;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6',
            'cache-control': 'no-cache',
            'dnt': '1',
            'pragma': 'no-cache',
            'referer': 'https://www.ishares.com/us/products/239707/ishares-russell-1000-etf',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }

        self._url = 'https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax'

    def _params(self, as_of_date: str = '') -> dict:
        as_of_date = as_of_date or _tcs.last_us_trade_day_before_today()
        return {
            'tab': 'all',
            'fileType': 'json',
            'asOfDate': as_of_date
        }

    def update_russell1000_tickers_from_ishare_2_db(self) -> bool:
        try:
            df = self.fetch_russell1000_tickers_from_ishare()
            if df.empty:
                _logger.warning(
                    'Failed to get russell1000_tickers from ishares')
                return False
            make_db_connection()
            if latest_as_of_date := _tm.get_latest_as_of_date_before():
                df.sort_values(by=['ticker'], inplace=True,
                               ascending=True, ignore_index=True)
                fetched_md5 = self._tickers_md5_from_df(df)
                tickers: QuerySet = Ticker.objects(
                    as_of_date=latest_as_of_date).order_by('ticker')
                local_md5 = self._tickers_md5_from_qs(tickers)
                if fetched_md5 and local_md5 and fetched_md5 == local_md5:
                    _logger.info('Same md5, update as_of_date')
                    if tickers.first().as_of_date != df['as_of_date'][0]:
                        tickers.update(as_of_date=df['as_of_date'][0])
                    else:
                        _logger.info('Even as_of_date unchanged,skip update')
                elif fetched_md5 and local_md5 or fetched_md5:
                    _logger.info('Diff md5, save new ones')
                    df_2_mongo(df, Ticker)
            else:
                # no older as of date, just store the data
                _logger.info('Maybe init update, save new ones')
                df_2_mongo(df, Ticker)
            return True
        except Exception as e:
            _logger.error(
                'Failed to get russell1000 tickers from ishare', exc_info=e)
            return False

    def _tickers_md5_from_df(self, df: DataFrame) -> str:
        # TODO: sort tickers before hashing
        if df.empty:
            return ''
        concated_tickers = reduce(lambda x, y: f'{x}{y}', df['ticker'].values)
        return hashlib.md5(concated_tickers.encode('utf-8')).hexdigest()

    def _tickers_md5_from_qs(self, qs: QuerySet) -> str:
        # TODO: sort tickers before hashing
        if qs.count() == 0:
            return ''
        concated_tickers = reduce(
            lambda x, y: f'{x.ticker if isinstance(x, Ticker) else x}{y.ticker}', qs)
        return hashlib.md5(concated_tickers.encode('utf-8')).hexdigest()

    def fetch_russell1000_tickers_from_ishare(self) -> DataFrame:
        """
        get holdings of russell1000 etf from ishare
        """
        try:
            _params = self._params()
            response = requests.get(
                self._url,
                params=_params,
                # cookies=cookies,
                headers=self._headers,
            )
            # _logger.debug(response.text)
            response.encoding = 'utf-8-sig'
            full_tickers = response.json()
            # _logger.debug(f'full_tickers: {full_tickers}')

            tickers = list(filter(
                lambda item: item[0] and item[0] != '-' and item[3] == 'Equity', full_tickers['aaData']))

            ticker_dict_list = [
                {'ticker': ticker[0], 'name': ticker[1], 'sector': ticker[2], 'cusip': ticker[8], 'isin': ticker[9],
                 'sedol': ticker[10]} for ticker in tickers]
            # _logger.debug(f'{ticker_dict_list}')

            df = DataFrame(ticker_dict_list)
            df['as_of_date'] = _params['asOfDate']
            df.dropna(inplace=True, ignore_index=True)
            return df
        except Exception as e:
            _logger.error(
                'Failed to get russell1000 tickers from ishare', exc_info=e, stack_info=True)
            return DataFrame()
