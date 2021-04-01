"""Monkay patch for cp.uptime()"""

import time

def uptime():
    return time.time()
