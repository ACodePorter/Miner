import unittest

from detonator import SingletonParent, get_logger

_logger = get_logger('SingletonTestCase')


class ChildSingleton1(SingletonParent):
    """
    Child class 1 inheriting from SingletonParent.
    """

    def __init__(self, value: str = 'ChildSingleton1'):
        self.value = value


class ChildSingleton2(SingletonParent):
    """
    Child class 2 inheriting from SingletonParent.
    """

    def __init__(self, value: str = "ChildSingleton2"):
        self.value = value


class SingletonTestCase(unittest.TestCase):
    def test_something(self):
        # Creating instances of child classes
        instance1 = ChildSingleton1.get_instance()
        instance11 = ChildSingleton1.get_instance()
        instance2 = ChildSingleton2.get_instance()

        # Both instances should be the same
        _logger.info(instance1.value)  # Output: ChildSingleton1
        _logger.info(instance2.value)  # Output: ChildSingleton2

        # Output: True (both instances are the same)
        _logger.info(instance1 is instance2)
        _logger.info(instance11 is instance1)

        self.assertIs(instance1, instance11)
        self.assertIsNot(instance1, instance2)


if __name__ == '__main__':
    unittest.main()
