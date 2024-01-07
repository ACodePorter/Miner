import os
import unittest

from mongoengine import connect
from yfinance import Ticker as YTicker

from dataminer import MarketDataShovel


class MarketDataShvelTestCase(unittest.TestCase):

    def setUp(self):
        connect('mongogo-test')
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


if __name__ == '__main__':
    unittest.main()
