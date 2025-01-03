import unittest
from datetime import datetime, timedelta

from dataminer import TradeCalendarShovel, MarketDataShovel
from detonator import make_db_connection, get_logger
from pytz import timezone

from marketbreadth import MarketBreadth

_default_start_date = datetime.now(
    timezone('America/New_York')) - timedelta(days=365)

_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
_mds: MarketDataShovel = MarketDataShovel.get_instance()
_logger = get_logger('UIB')


class MarketBreadthTestCase(unittest.TestCase):
    def test__update_index_breadth(self):
        make_db_connection(db='mongogo-test')
        mb: MarketBreadth = MarketBreadth.get_instance()
        mb.update_index_breadth('spx')

    def test_get_market_breath(self):
        make_db_connection()
        mb: MarketBreadth = MarketBreadth.get_instance()
        mbs = mb.get_market_breath()
        _logger.debug(type(mbs.to_json(orient='records')))


if __name__ == '__main__':
    unittest.main()
