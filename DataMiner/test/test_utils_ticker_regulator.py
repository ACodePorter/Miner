import unittest

from dataminer.utils import TickerRegulator


class TickerRegulatorTestCase(unittest.TestCase):
    def test_validate_ticker(self):
        regulator = TickerRegulator(cache_expiry_hours=1/900)

        # Test with a valid ticker
        valid_ticker = 'AAPL'
        result = regulator.validate_ticker(valid_ticker)
        self.assertEqual(result, 'AAPL')

        # Test with an invalid ticker
        invalid_ticker = 'INVALID'
        result = regulator.validate_ticker(invalid_ticker)
        self.assertEqual(result, '')

        # Test with an empty ticker
        empty_ticker = ''
        result = regulator.validate_ticker(empty_ticker)
        self.assertEqual(result, '')

        # Test with a ticker that needs to be transformed
        transformed_ticker = 'BRKA'
        result = regulator.validate_ticker(transformed_ticker)
        self.assertEqual(result, 'BRK-A')


if __name__ == '__main__':
    unittest.main()
