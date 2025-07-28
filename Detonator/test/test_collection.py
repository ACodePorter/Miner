import unittest

from detonator import common_in_list, get_logger, list_minus

_logger = get_logger('CollectionTestCase')


class CollectionTestCase(unittest.TestCase):
    def test_collection(self):
        l1 = ['1', '2', '3']
        l2 = ['3', '4', '5']
        _logger.debug(list_minus(l1, l2))
        _logger.debug(common_in_list(l1, l2))


if __name__ == '__main__':
    unittest.main()
