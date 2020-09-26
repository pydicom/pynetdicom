
import time

def sleep(duration):
    """Sleep for `duration` seconds."""
    now = time.perf_counter()
    end = now + duration
    while now < end:
        now = time.perf_counter()
