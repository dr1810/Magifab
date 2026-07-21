"""Bounded exponential retries shared by provider calls."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class RetryExhaustedError(RuntimeError):
    pass


class RetryExecutor:
    def __init__(self, attempts: int, base_delay_seconds: float) -> None:
        self._attempts = attempts
        self._base_delay_seconds = base_delay_seconds

    def run(self, action: Callable[[], T], *, on_attempt: Callable[[int, str, Exception | None], None]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            on_attempt(attempt, "started", None)
            try:
                result = action()
            except Exception as error:  # Providers intentionally expose varied transient exceptions.
                last_error = error
                on_attempt(attempt, "failed", error)
                if attempt < self._attempts:
                    time.sleep(self._base_delay_seconds * (2 ** (attempt - 1)))
                continue
            on_attempt(attempt, "succeeded", None)
            return result
        raise RetryExhaustedError(str(last_error) if last_error else "retry_attempts_exhausted") from last_error
