import time

class Cache:
    """Simple in‑memory cache with TTL."""
    def __init__(self, ttl=300):
        self.ttl = ttl
        self.data = {}

    def get(self, key):
        entry = self.data.get(key)
        if entry and time.time() - entry['timestamp'] < self.ttl:
            return entry['value']
        elif entry:
            del self.data[key]
        return None

    def set(self, key, value):
        self.data[key] = {
            'timestamp': time.time(),
            'value': value
        }

    def clear(self):
        self.data.clear()
