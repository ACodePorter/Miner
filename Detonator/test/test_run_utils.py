import logging
from datetime import datetime, time
from time import sleep
from typing import Any, Dict
from unittest import TestCase

import pytz
from detonator import IntradayTaskScheduler, get_logger
from detonator._run_utils import _convert_to_utc_time

_logger = get_logger('IntradayTaskSchedulerTestCase', logging.DEBUG)


class IntradayTaskSchedulerTestCase(TestCase):

    def setUp(self):
        self.scheduled: Dict[str, Any] = {}

    def test_is_time_to_run(self):
        now = datetime.now()
        scheduler = IntradayTaskScheduler(['1m', '5m', '10m', '15m', '30m', '65m'], func=self.interval_callback,
                                          start_time=time(
                                              hour=9, minute=30, tzinfo=pytz.timezone('America/New_York')),
                                          end_time=time(hour=16, minute=0, tzinfo=pytz.timezone('America/New_York')))
        current_time = datetime.combine(
            now.date(), time(hour=11, minute=40, second=10))
        yes = scheduler._is_time_to_run('65m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertTrue(yes)
        current_time = datetime.combine(
            now.date(), time(hour=11, minute=40, second=15))
        yes = scheduler._is_time_to_run('65m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertFalse(yes)
        current_time = datetime.combine(
            now.date(), time(hour=10, minute=40, second=15))
        yes = scheduler._is_time_to_run('65m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertFalse(yes)
        current_time = datetime.combine(now.date(), time(hour=10, second=15))
        yes = scheduler._is_time_to_run('30m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertFalse(yes)
        current_time = datetime.combine(now.date(), time(hour=10, second=9))
        yes = scheduler._is_time_to_run('30m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertTrue(yes)
        current_time = datetime.combine(
            now.date(), time(hour=10, minute=31, second=15))
        yes = scheduler._is_time_to_run('30m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertFalse(yes)
        current_time = datetime.combine(
            now.date(), time(hour=10, minute=30, second=10))
        yes = scheduler._is_time_to_run('30m', current_time, datetime.combine(now.date(), time(hour=9, minute=30)),
                                        datetime.combine(now.date(), time(hour=16)))
        self.assertTrue(yes)

    def interval_callback(self, interval):
        _logger.debug('interval_callback called: %s', interval)

    def test_scheduler(self):
        scheduler = IntradayTaskScheduler(intervals=['1m', '5m', '10m', '15m', '30m', '65m'], func=self.interval_callback,
                                          start_time=time(
                                              hour=9, minute=30, tzinfo=pytz.timezone('America/New_York')),
                                          end_time=time(hour=16, minute=0, tzinfo=pytz.timezone(
                                              'America/New_York')),
                                          schedule_delay=3)
        scheduler.start()
        sleep(180 * 60)
        scheduler.stop()

    def test_convert_to_utc_time(self):
        target = _convert_to_utc_time(
            time(hour=9, minute=30, tzinfo=pytz.timezone('America/New_York')))
        print(target)

    def tearDown(self):
        self.scheduled.clear()
