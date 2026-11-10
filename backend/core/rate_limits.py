"""Bounded, thread-safe counters for the single-process demo backend."""
import os
from threading import Lock
from time import monotonic


def positive_setting(name, default):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


class FixedWindow:
    def __init__(self, seconds, capacity=4096):
        self.seconds = seconds
        self.capacity = capacity
        self.lock = Lock()
        self.window = -1
        self.counts = {}

    def take(self, *limits):
        with self.lock:
            window = int(monotonic() // self.seconds)
            if window != self.window:
                self.window = window
                self.counts.clear()
            new_keys = sum(key not in self.counts for key, _ in limits)
            if len(self.counts) + new_keys > self.capacity:
                return False
            if any(self.counts.get(key, 0) >= limit for key, limit in limits):
                return False
            for key, _ in limits:
                self.counts[key] = self.counts.get(key, 0) + 1
            return True
