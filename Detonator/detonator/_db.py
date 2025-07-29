from functools import partial, wraps

from mongoengine import connect, get_connection
from mongoengine.connection import DEFAULT_CONNECTION_NAME

from ._env import is_prod
from ._log import get_logger

DEF_MONGO_HOST = 'miner-mongodb'
DEF_MONGO_PORT = 27017
DEF_MONGO_DB = 'mongogo'
_logger = get_logger('db')


def make_db_connection(db: str = DEF_MONGO_DB, host: str = DEF_MONGO_HOST, port=DEF_MONGO_PORT,
                       alias: str = DEFAULT_CONNECTION_NAME):
    try:
        get_connection(alias=alias)
    except Exception:
        prod = is_prod()
        _logger.info('Connecting to mongodb database prod: %s', prod)
        connect(db=db if prod else 'mongogo-test', host=host if prod else 'localhost', port=port, alias=alias,
                uuidRepresentation='standard', maxPoolSize=10, minPoolSize=5)


def ensure_db_connection(_func=None, *, db: str = DEF_MONGO_DB, host: str = DEF_MONGO_HOST, port=DEF_MONGO_PORT,
                         alias: str = DEFAULT_CONNECTION_NAME):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            make_db_connection(db=db, host=host, port=port, alias=alias)
            return func(*args, **kwargs)
        return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
