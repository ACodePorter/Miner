from celery import Celery
from celery.schedules import crontab
from detonator import get_logger, is_prod
from minerworkers import app

from ._ghpages_maintainer import GhPagesMaintainer
from .tasks import update_gh_pages_task

_logger = get_logger('Maintainer')

__all__ = ['GhPagesMaintainer', 'update_gh_pages_task']

app.autodiscover_tasks(packages=['maintainer'])


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    """
    Set up periodic tasks for Celery Beat.
    This function is connected to the `on_after_configure` signal.
    """
    if not is_prod():
        _logger.info('Skipping periodic tasks for non production environment')
        return
    # Add the daily update task.
    _logger.info(
        'Setting up periodic task for maintainer ...')
    sender.add_periodic_task(
        crontab(hour='*', minute='15'),
        update_gh_pages_task.s(),
        name='update-gh-pages',
        expires=600,
    )
