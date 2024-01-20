import unittest
from datetime import datetime, timedelta

from dataminer import TradeCalendarShovel, MarketDataShovel
from detonator import make_db_connection, get_logger
from pytz import timezone

from marketbreadth import MarketBreadth

make_db_connection(db='mongogo-test')

_default_start_date = datetime.now(timezone('America/New_York')) - timedelta(days=365)

_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
_mds: MarketDataShovel = MarketDataShovel.get_instance()
_logger = get_logger('UIB')


class MarketBreadthTestCase(unittest.TestCase):
    def test__update_index_breadth(self):
        mb: MarketBreadth = MarketBreadth.get_instance()
        mb.update_index_breadth('spx')


if __name__ == '__main__':
    unittest.main()
