from minerworkers import app
from ._version import __version__
from ._market_valuation_scraper import MarketValuationScraper
from .tasks import update_market_pe_task, update_hk_market_pe_task
from celery.schedules import crontab
from celery import Celery
from detonator import get_logger

_logger = get_logger('BrowserScraper')


__all__ = [
    '__version__',
    'MarketValuationScraper'
]

app.autodiscover_tasks(['browserscraper'], force=True)


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    """
    Set up periodic tasks for Celery Beat.
    This function is connected to the `on_after_configure` signal.
    """
    # Add the daily update task.
    _logger.info(
        'Setting up periodic task for browserscraper ...')
    sender.add_periodic_task(
        crontab(hour='*', minute='5', day_of_week='mon-fri'),
        update_market_pe_task.s(),
        name='update-market-pe-on-weekdays',
        expires=600,
    )
