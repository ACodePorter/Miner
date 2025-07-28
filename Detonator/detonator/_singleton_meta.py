from typing import Type, TypeVar

T = TypeVar('T', bound='SingletonParent')


class SingletonMeta(type):
    """
    Singleton metaclass to ensure that only one instance of each class is created.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SingletonParent(metaclass=SingletonMeta):
    """
    Singleton parent class with a get_instance function.
    """

    @classmethod
    def get_instance(cls: Type[T]) -> T:
        if cls not in cls._instances:
            cls._instances[cls] = cls()
        return cls._instances[cls]
