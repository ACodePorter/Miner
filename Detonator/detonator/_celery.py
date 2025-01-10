import os

def is_running_in_celery():
    return os.getenv("CELERY_WORKER_RUNNING") == "1"
