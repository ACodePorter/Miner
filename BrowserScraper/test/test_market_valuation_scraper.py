from unittest import TestCase
from browserscraper import MarketValuationScraper
from dataminer.models import MarketPe
import pandas as pd
from detonator import get_logger, make_db_connection

_logger = get_logger('MarketValuationScraperTestCase')


class MarketValuationScraperTestCase(TestCase):
    def setUp(self):
        make_db_connection()
        self.scraper = MarketValuationScraper()
        df = pd.read_csv('./spx_pe_ratio.csv')
        self.df = df
        _logger.info(self.df.dtypes)

    def test_to_db(self):
        """
        Test the scraping of the SP500 PE ratio table.
        """
        self.assertTrue(self.scraper._to_db(idx='spx', df=self.df),
                        "Failed to save SP500 PE ratio data to the database.")

    def test_update_idx_pe_to_db(self):
        """
        Test the scraping of the SP500 PE ratio table and saving to the database.
        """
        MarketPe.drop_collection()
        self.assertTrue(self.scraper.update_idx_pe_to_db(idx='qqq', start_date='2025,01,01',
                        end_date='2025,12,31'), "Failed to scrape and save SP500 PE ratio data to the database.")

    def test_sth(self):
        """
        Test the scraping of the SP500 PE ratio table.
        """
        self.scraper.update_idx_pe_to_latest(idx='qqq')
        self.scraper.update_idx_pe_to_latest(idx='spx')
