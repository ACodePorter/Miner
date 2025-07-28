from detonator import get_logger
from minerworkers import app

from ._ghpages_maintainer import GhPagesMaintainer

_logger = get_logger('Maintainer')


@app.task
def update_gh_pages_task() -> bool:
    print('update_gh_pages_task')
    m = GhPagesMaintainer.get_instance()
    m.update_gh_pages()
