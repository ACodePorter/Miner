import contextlib
import logging
from functools import wraps
from logging.handlers import RotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler

from ._path import to_real_abs_path

_DEFAULT_LOG_FORMAT = '[%(asctime)s.%(msecs)d %(levelname)s] %(name)s:%(funcName)s-> %(message)s'
_DEFAULT_LOG_DATE_FORMAT = '%Y%m%d %H%M%S'

logging.basicConfig(format=_DEFAULT_LOG_FORMAT, datefmt=_DEFAULT_LOG_DATE_FORMAT,
                    force=True, level=logging.INFO,
                    handlers=[RichHandler(rich_tracebacks=False, locals_max_string=1024, console=Console(width=240),
                                          show_level=False, show_time=False, show_path=False)])

with contextlib.suppress(Exception):
    import pandas as pd

    pd.set_option('display.max_columns', 480)
    pd.set_option('display.max_rows', 480)


class _Manager:
    _loggers = {}

    @staticmethod
    def get_logger(name, level=logging.DEBUG, storage_path: str = None) -> logging.Logger:
        if name in _Manager._loggers:
            return _Manager._loggers[name]
        logger = _Manager._create_logger(name, level, storage_path)
        _Manager._loggers[name] = logger
        return logger

    @staticmethod
    def _create_logger(name, level=logging.DEBUG, storage_path: str = None) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if storage_path := to_real_abs_path(storage_path):
            handler = RotatingFileHandler(
                storage_path, maxBytes=1024 * 1024 * 10, backupCount=10)
            handler.setFormatter(logging.Formatter(
                _DEFAULT_LOG_FORMAT, _DEFAULT_LOG_DATE_FORMAT))
            logger.addHandler(handler)
        return logger


def get_logger(name: str, level=logging.DEBUG, storage_path=None) -> logging.Logger:
    return _Manager.get_logger(name, level, storage_path)


def log_in_out(logger: logging.Logger):
    """
    Decorator to log input and output of function to specified logger
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if logger:
                logger.debug(f'{func.__name__}: {args} {kwargs}')
            result = func(*args, **kwargs)
            if logger:
                logger.debug(f'{func.__name__}-> {result}')
            return result

        return wrapper

    return decorator
