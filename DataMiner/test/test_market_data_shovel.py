import os
import unittest
from datetime import datetime

from mongoengine import connect
from yfinance import Ticker as YTicker

from dataminer import MarketDataShovel


class MarketDataShvelTestCase(unittest.TestCase):

    def setUp(self):
        connect('mongogo')
        os.environ['http_proxy'] = 'socks5://localhost:8001'
        os.environ['https_proxy'] = 'socks5://localhost:8001'

    def test_spx_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        md.update_spx_tickers()

    def test_update_ticker_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        md.update_ticker_info('aapl')

    def test_update_ticker_daily_info_to_db(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        yticker = YTicker('AAPL')
        md.fetch_ticker_daily_info_to_db(yticker, start_date='20240101')

    def test_update_ticker_daily_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        md.update_ticker_daily_info('AAPL')

    def test_get_latest_index_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        tickers = md.get_latest_index_tickers('spx')
        print(f'1tickers:{tickers}')
        print(f'2tickers:{list(tickers.tickers)}')

    def test_get_index_tickers_on(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        if it := md.get_index_tickers_on('spx'):
            print(it.tickers)
        else:
            print('Filed')

    def test_get_tickers_daily_info_on(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        print(md.get_tickers_daily_info_on(['AAPL', 'GOOGL'], '2024-01-12'))
        print(md.get_tickers_daily_info_on(
            ['AAPL', 'GOOGL'], datetime(year=2024, month=1, day=12)))


if __name__ == '__main__':
    unittest.main()
