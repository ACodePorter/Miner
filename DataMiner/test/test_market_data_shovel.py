import os
import unittest

from mongoengine import connect
from dataminer import MarketDataShovel


class MarketDataShvelTestCase(unittest.TestCase):

    def setUp(self):
        connect('mongogo-test')

    def test_spx_tickers(self):
        md:MarketDataShovel = MarketDataShovel.get_instance()
        md.update_spx_tickers()

    def test_update_ticker_info(self):
        os.environ['http_proxy'] = 'socks5://localhost:8001'
        os.environ['https_proxy'] = 'socks5://localhost:8001'
        md:MarketDataShovel = MarketDataShovel.get_instance()
        md.update_ticker_info('aapl')


if __name__ == '__main__':
    unittest.main()
