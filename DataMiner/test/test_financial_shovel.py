import os
from unittest import TestCase

from detonator import get_logger, make_db_connection

from dataminer import FinancialShovel

_logger = get_logger('FinancialShovelTestCase')


class FinancialShovelTestCase(TestCase):
    def setUp(self):
        make_db_connection(db='miner-test')
        pass
        os.environ['HTTP_PROXY'] = 'socks5://localhost:8001'
        os.environ['HTTPS_PROXY'] = 'socks5://localhost:8001'

    def test_financial_shovel(self):
        fs = FinancialShovel.get_instance()
        fs.financial_reports_2_db('googl', freq='quarterly')
