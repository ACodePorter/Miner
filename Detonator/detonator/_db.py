from mongoengine import connect, get_connection
from mongoengine.connection import DEFAULT_CONNECTION_NAME


def make_db_connection(db: str = 'mongogo', host: str = 'localhost', port=27017, alias: str = DEFAULT_CONNECTION_NAME):
    try:
        get_connection()
    except Exception:
        connect(db=db, host=host, port=port, alias=alias)


def ensure_db_connection(db: str = 'mongogo', host: str = 'localhost', port=27017,
                         alias: str = DEFAULT_CONNECTION_NAME):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Connect to MongoDB if not already connected
            make_db_connection(db=db, host=host, port=port, alias=alias)
            # Call the original function
            return func(*args, **kwargs)

        return wrapper

    return decorator
