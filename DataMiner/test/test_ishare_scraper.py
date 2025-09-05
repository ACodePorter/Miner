import unittest

from dataminer import IsharesScraper
from detonator import get_logger, make_db_connection

_logger = get_logger('IsharesScraperTestCase')


class IsharesScraperTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection()

    def test_ishare_shovel(self):
        ishare: IsharesScraper = IsharesScraper.get_instance()
        self.assertFalse(ishare.fetch_iwm_tickers().empty,
                         'Failed to fetch iwm tickers')
        self.assertFalse(ishare.fetch_iwd_tickers().empty,
                         'Failed to fetch iwd tickers')
        self.assertFalse(ishare.fetch_iwf_tickers().empty,
                         'Failed to fetch iwf tickers')


if __name__ == '__main__':
    unittest.main()
