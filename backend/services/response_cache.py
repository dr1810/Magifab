"""Thread-safe, versioned in-memory response cache with single-flight request sharing."""
from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock
from typing import Callable

from config import Settings
from schemas.personalization import GPTPersonalizationResponse


class ResponseCache:
    """Caches personalized wording by knowledge revision and shares concurrent cache misses."""

    def __init__(self, settings: Settings):
        self._maximum_entries = settings.response_cache_max_entries
        self._entries: OrderedDict[str, GPTPersonalizationResponse] = OrderedDict()
        self._pending: dict[str, Future[GPTPersonalizationResponse]] = {}
        self._lock = Lock()

    def get_or_create(self, key: str, create: Callable[[], GPTPersonalizationResponse]) -> tuple[GPTPersonalizationResponse, bool]:
        """Return cached text or share a single in-flight provider request for the same key."""
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached, True
            pending = self._pending.get(key)
            owner = pending is None
            if owner:
                pending = Future()
                self._pending[key] = pending
        if not owner:
            return pending.result(), True
        try:
            response = create()
            with self._lock:
                self._entries[key] = response
                self._entries.move_to_end(key)
                while len(self._entries) > self._maximum_entries:
                    self._entries.popitem(last=False)
                pending.set_result(response)
            return response, False
        except BaseException as error:
            with self._lock:
                pending.set_exception(error)
            raise
        finally:
            with self._lock:
                self._pending.pop(key, None)
