from unittest import TestCase

from dataminer import WedgePop
from detonator import make_db_connection


class WedgePopTestCase(TestCase):

    def setUp(self):
        make_db_connection()

    def test_update_wedge_pop(self):
        wedge_pop = WedgePop.get_instance()
        self.assertTrue(wedge_pop.update_wedge_pop('GOOGL'))
        self.assertTrue(wedge_pop.update_wedge_pop('TSLA'))

    def test_get_wedge_tickers_since(self):
        wedge_pop = WedgePop.get_instance()
        tickers = wedge_pop.get_wedge_tickers_since('20240101')
        print(tickers)
        self.assertTrue(len(tickers) > 0)
