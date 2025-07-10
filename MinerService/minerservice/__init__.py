from celery.schedules import crontab
from minerworkers import app
from dataminer.tasks import run_daily_updates_task
from celery import Celery
from detonator import get_logger

from ._version import version

__all__ = [
    'version'
]

_logger = get_logger('MinerService')

app.autodiscover_tasks(['dataminer', 'marketbreadth'], force=True)


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    """
    Set up periodic tasks for Celery Beat.
    This function is connected to the `on_after_configure` signal.
    """
    # Add the daily update task.
    _logger.info('Setting up periodic task \'daily-1630-updates\'...')
    sender.add_periodic_task(
        crontab(hour=16, minute=30, day_of_week='mon-fri'),
        run_daily_updates_task.s(),
        name='daily-1630-updates',
        expires=600,
    )
