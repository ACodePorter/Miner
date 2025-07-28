import os
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from random import random
from typing import Any, Callable, List

from ._env import is_in_daemon


def sleep(mi: float = 1, ma: float = 6):
    r = random()
    if r > 0.99:
        time.sleep(ma + (ma - mi) * r)
    elif r < 0.01:
        time.sleep(mi * r)
    else:
        time.sleep(mi + (ma - mi) * r)


def run_parallel(func: Callable[[Any], Any], args: List[Any], num_workers: int = os.cpu_count() or 4) -> List[Any]:
    if is_in_daemon():
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            result: List[Any] = list(executor.map(func, args))
    else:
        with Pool(processes=num_workers) as p:
            result: List[Any] = p.map(func, args)
    return result
