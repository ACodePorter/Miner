from mongoengine import connect, get_connection


def ensure_db_connection(func):
    def wrapper(*args, **kwargs):
        # Connect to MongoDB if not already connected

        try:
            get_connection()
        except Exception:
            connect(db='mongogo')

        # Call the original function
        return func(*args, **kwargs)

    return wrapper
