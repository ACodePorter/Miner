import unittest

from russell1000miner.utils import get_logger


class LogTestCase(unittest.TestCase):
    def test_get_logger(self):
        logger_a1 = get_logger('a')
        logger_a2 = get_logger('a')
        self.assertEqual(logger_a1, logger_a2)
        logger = logger_a1
        logger.fatal('fatal')
        logger.exception('exception')
        logger.warning('warning')
        logger.info('info')
        logger.debug('debug')


if __name__ == '__main__':
    unittest.main()
