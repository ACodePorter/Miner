from unittest import TestCase

from minerworkers import test_task_a
from minerworkers.tasks import this_another_test_task, this_is_the_test_task


class TasksTestCase(TestCase):
    def test_test_task(self):
        this_is_the_test_task.delay()

    def test_another_test_task(self):
        this_another_test_task.delay()

    def test_test_task_a(self):
        test_task_a.delay()
