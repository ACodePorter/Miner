from celery.schedules import crontab
from minerworkers import app
from dataminer.tasks import run_daily_updates_task, update_hk_all_task
from celery import Celery
from detonator import get_logger
from marketbreadth.tasks import update_spx_market_breadth_task

from ._version import version

__all__ = [
    'version'
]

_logger = get_logger('MinerService')

app.autodiscover_tasks(['dataminer', 'marketbreadth'], force=True)


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **_):
    """
    Set up periodic tasks for Celery Beat.
    This function is connected to the `on_after_configure` signal.
    """
    _logger.info('Setting up miner service periodic tasks ...')
    sender.add_periodic_task(
        crontab(hour=16, minute=5, day_of_week='mon-fri'),
        run_daily_updates_task.s(),
        name='us-daily-1630-updates',
        expires=600,
    )

    sender.add_periodic_task(
        crontab(hour=5, minute=1, day_of_week='mon-fri'),
        update_hk_all_task.s(),
        name='hk-daily-idx-updates',
        expires=600,
    )

    sender.add_periodic_task(
        crontab(hour="19-23", minute=30, day_of_week='mon-fri'),
        update_spx_market_breadth_task.s(),
        name='update-spx-market-breadth-hourly-evening',
        expires=600,
    )
    _logger.info('Miner service periodic tasks setup complete')


_logger.info('Miner service initialized...')
