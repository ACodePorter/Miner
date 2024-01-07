import unittest
from detonator import  add_minus_to_YYYYmmdd, remove_minus_in_YYYYmmdd


class CalendarTestCase(unittest.TestCase):
    def test_add_n_remove(self):
        YYYYmmdd = '20240404'
        self.assertEqual('2024-04-04', add_minus_to_YYYYmmdd(YYYYmmdd))
        self.assertEqual(YYYYmmdd, remove_minus_in_YYYYmmdd('2024-04-04'))


if __name__ == '__main__':
    unittest.main()
