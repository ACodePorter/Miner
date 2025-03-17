from mongoengine import connect, get_connection
from mongoengine.connection import DEFAULT_CONNECTION_NAME

DEF_MONGO_HOST = 'miner-mongodb'
DEF_MONGO_PORT = 27017
DEF_MONGO_DB = 'mongogo'


def make_db_connection(db: str = DEF_MONGO_DB, host: str = DEF_MONGO_HOST, port=DEF_MONGO_PORT,
                       alias: str = DEFAULT_CONNECTION_NAME):
    try:
        get_connection(alias=alias)
    except Exception:
        connect(db=db, host=host, port=port, alias=alias)


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
