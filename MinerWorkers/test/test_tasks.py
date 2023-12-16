from unittest import TestCase

from minerworkers.tasks import this_is_the_test_task, this_another_test_task
from minerworkers import test_task_a


class TasksTestCase(TestCase):
    def test_test_task(self):
        this_is_the_test_task.delay()

    def test_another_test_task(self):
        this_another_test_task.delay()

    def test_test_task_a(self):
        test_task_a.delay()
