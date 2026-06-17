"""
LRU cache for midway buffers.
"""

from collections import OrderedDict
from typing import Optional


class MidwayCache:
    def __init__(self, max_entries: int = 4):
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._max = max_entries

    def get(self, xxx_path: str) -> Optional[bytes]:
        if xxx_path in self._cache:
            self._cache.move_to_end(xxx_path)
            return self._cache[xxx_path]
        return None

    def put(self, xxx_path: str, buffer: bytes):
        self._cache[xxx_path] = buffer
        self._cache.move_to_end(xxx_path)
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def evict(self, xxx_path: str):
        self._cache.pop(xxx_path, None)

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def memory_usage(self) -> int:
        return sum(len(b) for b in self._cache.values())
