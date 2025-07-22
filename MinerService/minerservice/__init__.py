from celery.schedules import crontab
from minerworkers import app
from dataminer.tasks import run_daily_updates_task, update_hk_all_task
from celery import Celery, chain
from detonator import get_logger
from marketbreadth.tasks import update_spx_market_breadth_task

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
    us_daily_chain = chain(
       run_daily_updates_task.si(),
       update_spx_market_breadth_task.si()
    )

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
        update_hk_all_task.s(),
        name='hk-daily-idx-updates',
        expires=600,
    )
    _logger.info('Miner service periodic tasks setup complete')

_logger.info('Miner service initialized...')
