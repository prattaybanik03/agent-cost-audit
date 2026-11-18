"""Reference solution. Never shown to a model."""

from collections import OrderedDict

_MISSING = object()


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._items = OrderedDict()

    def get(self, key, default=None):
        value = self._items.get(key, _MISSING)
        if value is _MISSING:
            return default
        self._items.move_to_end(key)
        return value

    def peek(self, key, default=None):
        return self._items.get(key, default)

    def put(self, key, value):
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key)
            return None
        self._items[key] = value
        if len(self._items) > self._capacity:
            evicted, _ = self._items.popitem(last=False)
            return evicted
        return None

    def delete(self, key):
        if key in self._items:
            del self._items[key]
            return True
        return False

    def keys(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def __contains__(self, key):
        return key in self._items
