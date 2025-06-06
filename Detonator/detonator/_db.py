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
                uuidRepresentation='standard')


def ensure_db_connection(db: str = DEF_MONGO_DB, host: str = DEF_MONGO_HOST, port=DEF_MONGO_PORT,
                         alias: str = DEFAULT_CONNECTION_NAME):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Connect to MongoDB if not already connected
            make_db_connection(db=db, host=host, port=port, alias=alias)
            # Call the original function
            return func(*args, **kwargs)

        return wrapper

    return decorator
