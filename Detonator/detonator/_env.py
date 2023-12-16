import os


def is_in_docker() -> bool:
    return os.path.exists('/.dockerenv')
