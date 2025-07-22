from celery.schedules import crontab
from minerworkers import app
from dataminer.tasks import us_task_chain, hk_task_chain
from celery import Celery, chain
from detonator import get_logger
from marketbreadth.tasks import update_spx_market_breadth_task
from ._chains import us_daily_chain, hk_daily_chain

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
    _logger.info('Setting up miner service periodic tasks ...')
    sender.add_periodic_task(
        crontab(hour=16, minute=30, day_of_week='mon-fri'),
        us_daily_chain,
        name='us-daily-1630-updates',
        expires=600,
    )

    # 17:15 Hong Kong time (Asia/Hong_Kong) explicitly set
    sender.add_periodic_task(
        crontab(hour=5, minute=15, day_of_week='mon-fri'),
        hk_daily_chain,
        name='hk-daily-updates',
        expires=600,
    )
    _logger.info('Miner service periodic tasks setup complete')

_logger.info('Miner service initialized...')
