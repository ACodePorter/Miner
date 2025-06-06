import unittest
from datetime import datetime

from dataminer import MarketDataShovel
from detonator import make_db_connection
from yfinance import Ticker as YTicker


class MarketDataShvelTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection()

    def test_update_spx_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_spx_tickers(),
                        'Failed to update SPX tickers')

    def test_update_iwd_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwd_tickers(),
                        'Failed to update IWD tickers')

    def test_update_iwf_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwf_tickers(),
                        'Failed to update iwf tickers')

    def test_update_iwm_tickers(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwm_tickers(),
                        'Failed to update IWM tickers')

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

    def test_update_spx_tickers_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        md.update_spx_tickers_info()

    def test_update_spx_tickers_daily_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        md.update_spx_tickers_daily_info()

    def test_update_iwd_tickers_daily_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwd_tickers_daily_info(),
                        'Failed to update IWD tickers daily info')

    def test_update_iwf_tickers_daily_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwf_tickers_daily_info(),
                        'Failed to update iwf tickers daily info')

    def test_update_iwm_tickers_daily_info(self):
        md: MarketDataShovel = MarketDataShovel.get_instance()
        self.assertTrue(md.update_iwm_tickers_daily_info(),
                        'Failed to update IWM tickers daily info')


if __name__ == '__main__':
    unittest.main()
