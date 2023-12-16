from . import app
from detonator import get_logger

_logger = get_logger(__name__)


@app.task
def this_is_the_test_task():
    _logger.info('ZZZZZZZZ this is the test task')


@app.task
def this_another_test_task():
    _logger.error('############# this is another test task')
