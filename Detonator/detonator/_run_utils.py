import time
from random import random


def sleep(mi: float = 1, ma: float = 6):
    r = random()
    if r > 0.99:
        time.sleep(ma + (ma - mi) * r)
    elif r < 0.01:
        time.sleep(mi * r)
    else:
        time.sleep(mi + (ma - mi) * r)
