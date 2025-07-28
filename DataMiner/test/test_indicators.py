import datetime
import unittest

from dataminer import Indicators
from dataminer._indicators import (_calculate_indicator,
                                   _get_since_trade_date_for_indicator)
from detonator import get_logger, make_db_connection
from pandas import DataFrame
from pymongo import MongoClient

_l = get_logger('IndicatorsTestCase')


class IndicatorsTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection()
        self._client = MongoClient('localhost', 27017)

    def tearDown(self):
        if self._client:
            self._client.close()
            self._client = None

    def test_update_spx_daily_sma(self):
        indicators: Indicators = Indicators.get_instance()
        ret = indicators.update_spx_daily_sma()
        _l.debug(ret)

    def test_get_since_trade_date_for_indicator(self):
        ticker = 'AAPL'
        indicator = 'sma'
        interval = '1d'
        period = 20
        now = datetime.datetime.now()
        since_date = _get_since_trade_date_for_indicator(
            ticker, indicator, interval, period)
        _l.debug((datetime.datetime.now() - now).total_seconds())
        _l.debug(
            f'Since date for {ticker} {indicator}{period} is {since_date}')
        self.assertIsNotNone(since_date)

    def test_db_perf(self):
        now = datetime.datetime.now()
        aapl = self._client['mongogo-test']['ticker_daily_info'].find({'ticker': 'AAPL', 'interval': '1d'}).sort(
            'trade_date', 1)
        a_list = list(aapl)
        a_df = DataFrame(a_list)
        _l.debug((datetime.datetime.now() - now).total_seconds())
        _l.debug(a_list[:5])
        _l.debug(a_df.sample(4))

    def test_calculate_indicator(self):
        _calculate_indicator('AAPL', 'sma', '20250101', '1d', 10)

    def test_update_indicators_for_tickers(self):
        indicators: Indicators = Indicators.get_instance()
        ret = indicators.update_indicators_for_tickers(['GOOGL', 'TSLA'])
        _l.debug(ret)


if __name__ == '__main__':
    unittest.main()
