import unittest
from datetime import datetime, timedelta

from dataminer import TradeCalendarShovel, MarketDataShovel
from detonator import make_db_connection, get_logger
from pytz import timezone

from marketbreadth import MarketBreadth

_default_start_date = datetime.now(
    timezone('America/New_York')) - timedelta(days=7)

_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
_mds: MarketDataShovel = MarketDataShovel.get_instance()
_logger = get_logger('MarketBreadthTestCase')


class MarketBreadthTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection()

    def test__update_index_breadth(self):
        mb: MarketBreadth = MarketBreadth.get_instance()
        mb.update_index_breadth('spx')

    def test_get_market_breath(self):
        mb: MarketBreadth = MarketBreadth.get_instance()
        mbs = mb.get_market_breath()
        _logger.debug(type(mbs.to_json(orient='records')))


if __name__ == '__main__':
    unittest.main()
