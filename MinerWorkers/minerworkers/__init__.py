from celery import Celery
from detonator import get_logger

from ._version import version

_logger = get_logger('MinerWorkers')

app = Celery('Miner')
app.config_from_object('minerworkers.celeryconfig')
app.autodiscover_tasks(['minerworkers'], force=True)

# @app.task
# def test_task_a():
#     _logger.error('This is test task a')


__all__ = [
    'version',
]
