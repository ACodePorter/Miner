import os

from multiprocessing import current_process


def is_in_docker() -> bool:
    return os.path.exists('/.dockerenv')


def is_in_daemon() -> bool:
    return current_process().daemon
