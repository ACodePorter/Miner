import datetime

import pytz
import requests
from pandas import DataFrame

from .ticker import Ticker
from detonator import get_logger, df_2_mongo, ensure_db_connection

_logger = get_logger('IsharesShovel')


class IsharesShovel(object):
    headers = {
        'authority': 'www.ishares.com',
        'accept': '*/*',
        'accept-language': 'en-US,en-CA;q=0.9,en;q=0.8,zh-CN;q=0.7,zh;q=0.6',
        'cache-control': 'no-cache',
        'dnt': '1',
        'pragma': 'no-cache',
        'referer': 'https://www.ishares.com/us/products/239707/ishares-russell-1000-etf',
        'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    as_of_date = (datetime.datetime.now(pytz.timezone('America/New_York')) - datetime.timedelta(days=1)).strftime(
        '%Y%m%d')
    params = {
        'tab': 'all',
        'fileType': 'json',
        'asOfDate': as_of_date
    }

    url = 'https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax'

    @ensure_db_connection
    def get(self) -> DataFrame:
        response = requests.get(
            IsharesShovel.url,
            params=IsharesShovel.params,
            # cookies=cookies,
            headers=IsharesShovel.headers,
        )
        # _logger.debug(response.text)
        response.encoding = 'utf-8-sig'
        full_tickers = response.json()

        tickers = list(filter(
            lambda item: item[0] and item[0] != '-' and item[3] == 'Equity', full_tickers['aaData']))

        ticker_dict_list = [
            {'ticker': ticker[0], 'name': ticker[1], 'sector': ticker[2], 'cusip': ticker[8], 'isin': ticker[9],
             'sedol': ticker[10]} for ticker in tickers]

        df = DataFrame(ticker_dict_list)
        df['as_of_date'] = (
            datetime.datetime.now(pytz.timezone('America/New_York')) - datetime.timedelta(days=1)).strftime(
            '%Y%m%d')
        df.dropna(inplace=True, ignore_index=True)
        df_2_mongo(df, Ticker)
        return df
