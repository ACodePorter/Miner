import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import time as datetime_time
from datetime import timedelta, timezone
from multiprocessing import Pool
from random import random
from threading import Thread
from typing import Any, Callable, List, Optional

import pytz

from ._env import is_in_daemon
from ._log import get_logger


def sleep(mi: float = 1, ma: float = 6):
    r = random()
    if r > 0.99:
        time.sleep(ma + (ma - mi) * r)
    elif r < 0.01:
        time.sleep(mi * r)
    else:
        time.sleep(mi + (ma - mi) * r)


def run_parallel(func: Callable[[Any], Any], args: List[Any], num_workers: int = os.cpu_count() + 1 or 4) -> List[Any]:
    if is_in_daemon():
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            result: List[Any] = list(executor.map(func, args))
    else:
        with Pool(processes=num_workers) as p:
            result: List[Any] = p.map(func, args)
    return result


def _convert_to_utc_time(time_obj: datetime_time) -> datetime_time:
    """
    Convert a time object to UTC time.

    Args:
        time_obj: The time object to convert

    Returns:
        UTC time object

    """
    # Get current date
    today = datetime.now(time_obj.tzinfo).date()
    print(time_obj)
    print(today)

    # Use local system timezone
    # source_datetime = datetime.combine(today, time_obj, tzinfo=time_obj.tzinfo)
    naive = datetime.combine(today, time_obj.replace(tzinfo=None))
    localized = time_obj.tzinfo.localize(naive)  # correct DST offset
    utc_dt = localized.astimezone(pytz.UTC)
    return utc_dt.time()


class IntradayTaskScheduler:
    '''
    run interval based intraday task, the intervals must be in minutes for now, like 5m, 10m,15m,30m, 65m
    '''
    SUPPORTED_INTERVALS = ['1m', '5m', '10m', '15m', '30m', '65m']
    TORLENCE_SECONDS = 10

    def __init__(self, intervals: str | list[str], func: Callable[[List[str]], Any], start_time: datetime_time,
                 end_time: datetime_time, schedule_delay: float = 0):
        self.logger = get_logger('IntradayTaskScheduler', logging.DEBUG)
        if isinstance(intervals, str):
            intervals = [intervals]
        if not all([i in self.SUPPORTED_INTERVALS for i in intervals]):
            raise ValueError(
                f'intervals must be in {self.SUPPORTED_INTERVALS}')
        self.intervals = intervals
        self.intervals.sort()
        self.logger.debug(f'intervals: {self.intervals}')
        if not self.intervals:
            raise ValueError('intervals can not be empty')
        if not func or not callable(func):
            raise ValueError(f'func must be callable:{func}')
        self.func = func
        self.thread: Optional[Thread] = None
        self.start_time: datetime_time = _convert_to_utc_time(start_time)
        self.end_time: datetime_time = _convert_to_utc_time(end_time)
        self.schedule_delay: float = schedule_delay
        self.running = False

    def start(self):
        try:
            if not self.running:
                self.running = True
                self.thread = Thread(target=self._run_scheduler, daemon=True)
                self.thread.start()
        except Exception as e:
            self.logger.error(e)

    def stop(self):
        try:
            self.running = False
            if self.thread and self.thread.is_alive():
                self.thread.join()
                self.thread = None
        except Exception as e:
            self.logger.error(e)

    def _get_next_65m_update_time(self, current_time: datetime, start: datetime, end: datetime) -> datetime:
        """Calculate next 65m update time based on market session"""

        # Check if current time aligns with 65-minute boundaries
        elapsed_from_open = current_time - start
        elapsed_minutes = elapsed_from_open.total_seconds() / 60

        # 65-minute boundaries: 0, 65, 130, 195, 260, 325 minutes from market open
        if elapsed_minutes % 65 == 0:
            # We're exactly at a boundary, next update in 65 minutes
            return current_time + timedelta(minutes=65)
        else:
            # Calculate next boundary
            next_boundary = ((int(elapsed_minutes) // 65) + 1) * 65
            return start + timedelta(minutes=next_boundary)

    def _get_next_update_time(self, current_time: datetime, interval: str, start: datetime, end: datetime) -> datetime:
        """Calculate the next update time for a given interval"""
        if interval == '1m':
            # Next minute at :00 seconds
            return current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        elif interval == '5m':
            # Next 5-minute boundary (00, 05, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)
            current_minute = current_time.minute
            next_5min_boundary = ((current_minute // 5) + 1) * 5
            if next_5min_boundary >= 60:
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                return current_time.replace(minute=next_5min_boundary, second=0, microsecond=0)

        elif interval == '15m':
            # Next 15-minute boundary (00, 15, 30, 45)
            current_minute = current_time.minute
            next_15min_boundary = ((current_minute // 15) + 1) * 15
            if next_15min_boundary >= 60:
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                return current_time.replace(minute=next_15min_boundary, second=0, microsecond=0)

        elif interval == '30m':
            # Next 30-minute boundary (00, 30)
            current_minute = current_time.minute
            if current_minute < 30:
                return current_time.replace(minute=30, second=0, microsecond=0)
            else:
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        elif interval == '65m':
            # Market session based (09:30, 10:35, 11:40, 12:45, 13:50, 14:55, 16:00)
            return self._get_next_65m_update_time(current_time, start, end)

        return current_time + timedelta(minutes=1)  # Default fallback

    def _calculate_optimal_sleep_time(self, current_time: datetime, start: datetime, end: datetime) -> float:
        """Calculate optimal sleep time to align with next update opportunity

        This method ensures the thread wakes up at exactly the right time
        for the next bar update, providing precise timing synchronization.
        """
        # Find the next update time for any interval
        next_update_times = []

        for interval in self.intervals:
            next_time = self._get_next_update_time(
                current_time, interval, start, end)
            if next_time:
                next_update_times.append(next_time)

        if not next_update_times:
            return 60.0  # Default to 1 minute if no valid times

        # Find the earliest next update time
        next_update = min(next_update_times)

        # Calculate sleep time
        sleep_seconds = (next_update - current_time).total_seconds()

        # Add a small buffer (50ms) to ensure we wake up slightly before the target time
        # This helps compensate for any system scheduling delays
        sleep_seconds = max(0.05, sleep_seconds - 0.05)
        # FIXME: for now, the scheduler is used for fetching bars, so we delay 3 second to allow the bars to be completed
        sleep_seconds += self.schedule_delay
        # Ensure we don't sleep for negative time
        return sleep_seconds if sleep_seconds >= 0 else 1.0

    def _run_scheduler(self):
        """Internal method to run the scheduler loop."""
        while self.running:
            current_time = datetime.now(tz=timezone.utc)
            start = current_time.combine(
                current_time.date(), self.start_time, timezone.utc)
            end = current_time.combine(
                current_time.date(), self.end_time, timezone.utc)
            to_run_intervals = {i if self._is_time_to_run(
                i, current_time, start, end) else '' for i in self.intervals}
            to_run_intervals.discard('')
            self.logger.debug(to_run_intervals)
            if to_run_intervals:
                self.func(list(to_run_intervals))
            to_sleep = self._calculate_optimal_sleep_time(
                datetime.now(tz=timezone.utc), start, end)
            self.logger.debug(to_sleep)
            time.sleep(to_sleep)

    def _is_time_to_run(self, interval: str, current_time: datetime, start_time: datetime, end_time: datetime) -> bool:
        end_time += timedelta(seconds=self.schedule_delay + 5)
        self.logger.debug('%s %s %s %s', interval,
                          current_time, start_time, end_time)
        if start_time <= current_time <= end_time:
            if interval == '1m':
                return current_time.second <= self.TORLENCE_SECONDS
            elif interval == '5m':
                return current_time.minute % 5 == 0 and current_time.second <= self.TORLENCE_SECONDS
            elif interval == '10m':
                return current_time.minute % 10 == 0 and current_time.second <= self.TORLENCE_SECONDS
            elif interval == '15m':
                return current_time.minute % 15 == 0 and current_time.second <= self.TORLENCE_SECONDS
            elif interval == '30m':
                return current_time.minute % 30 == 0 and current_time.second <= self.TORLENCE_SECONDS
            elif interval == '65m':
                return int((
                    current_time - start_time).total_seconds() / 60) % 65 == 0 and current_time.second <= self.TORLENCE_SECONDS
        return False
