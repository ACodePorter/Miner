import time
from random import random


def sleep(mi: float = 3, ma: float = 8):
    if random() > 0.99:
        time.sleep(ma + (ma - mi) * random())
    elif random() < 0.01:
        time.sleep(mi * random())
    else:
        time.sleep(mi + (ma - mi) * random())
