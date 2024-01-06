import hashlib
from functools import reduce
from typing import Iterable


def md5_str(the_str: str) -> str:
    return hashlib.md5(the_str.encode('utf-8')).hexdigest() if the_str else ''


def md5_iterable(iterable: Iterable) -> str:
    full_str = reduce(lambda x, y: x + str(y), iterable, '')
    return md5_str(full_str) if full_str else ''
