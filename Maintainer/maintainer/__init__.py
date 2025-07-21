from ._ghpages_maintainer import GhPagesMaintainer
from minerworkers import app
from celery.schedules import crontab
from celery import Celery
from .tasks import update_gh_pages_task
from detonator import get_logger

_logger = get_logger('Maintainer')

__all__ = ['GhPagesMaintainer', 'update_gh_pages_task']

app.autodiscover_tasks(packages=['maintainer'])

@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    """
    Set up periodic tasks for Celery Beat.
    This function is connected to the `on_after_configure` signal.
    """
    # Add the daily update task.
    _logger.info(
        'Setting up periodic task for maintainer ...')
    sender.add_periodic_task(
        crontab(hour='*/2', minute='15'),
        update_gh_pages_task.s(),
        name='update-gh-pages',
        expires=600,
    )
