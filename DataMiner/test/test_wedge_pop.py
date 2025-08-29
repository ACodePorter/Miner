from unittest import TestCase

from detonator import make_db_connection

from dataminer import WedgePop


class WedgePopTestCase(TestCase):

    def setUp(self):
        make_db_connection()

    def test_update_wedge_pop(self):
        wedge_pop = WedgePop.get_instance()
        self.assertTrue(wedge_pop.update_wedge_pop('GOOGL'))
        self.assertTrue(wedge_pop.update_wedge_pop('TSLA'))
        self.assertTrue(wedge_pop.update_wedge_pop('ZM'))

    def test_get_wedge_tickers_since(self):
        wedge_pop = WedgePop.get_instance()
        tickers = wedge_pop.get_wedge_tickers_since('20240101')
        print(tickers)
        self.assertTrue(len(tickers) > 0)

    def test_get_wedge_tickers_on_today(self):
        wedge_pop = WedgePop.get_instance()
        tickers = wedge_pop.get_wedge_tickers_on_today()
        print(tickers)
        self.assertTrue(len(tickers) > 0)

    def test_get_wedge_stats(self):
        wedge_pop = WedgePop.get_instance()
        stats = wedge_pop.get_wedge_stats()
        print(stats)
        self.assertTrue(len(stats) > 0)
