import os
from typing import Optional


def expand_user_path(path: str) -> Optional[str]:
    return os.path.expanduser(path) if path and path.startswith('~') else path


def to_real_abs_path(path: str) -> str:
    if path:
        path = expand_user_path(path)
        path = os.path.relpath(path) if os.path.islink(path) else path
        path = path if os.path.isabs(path) else os.path.abspath(path)
    return path
