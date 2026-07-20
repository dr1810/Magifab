"""Bounded per-conversation memory for follow-up question resolution."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    answer: str


class ConversationMemory:
    def __init__(self, max_turns: int = 12) -> None:
        self._max_turns = max_turns
        self._turns: dict[str, deque[ConversationTurn]] = defaultdict(lambda: deque(maxlen=max_turns))
        self._lock = Lock()

    def recall(self, key: str) -> tuple[ConversationTurn, ...]:
        with self._lock:
            return tuple(self._turns[key])

    def remember(self, key: str, question: str, answer: str) -> None:
        with self._lock:
            self._turns[key].append(ConversationTurn(question=question, answer=answer))


class FileConversationMemory(ConversationMemory):
    """Durable bounded conversation turns without exposing a user identifier in paths."""

    def __init__(self, root: Path, max_turns: int = 12) -> None:
        super().__init__(max_turns=max_turns)
        self._root = root

    def recall(self, key: str) -> tuple[ConversationTurn, ...]:
        with self._lock:
            turns = self._load(key)
            self._turns[key] = deque(turns, maxlen=self._max_turns)
            return tuple(turns)

    def remember(self, key: str, question: str, answer: str) -> None:
        with self._lock:
            turns = self._load(key)
            turns.append(ConversationTurn(question=question, answer=answer))
            turns = turns[-self._max_turns:]
            self._turns[key] = deque(turns, maxlen=self._max_turns)
            self._root.mkdir(parents=True, exist_ok=True)
            target = self._path(key)
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps([turn.__dict__ for turn in turns]), encoding="utf-8")
            temporary.replace(target)

    def _load(self, key: str) -> list[ConversationTurn]:
        path = self._path(key)
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return [ConversationTurn(question=item["question"], answer=item["answer"]) for item in payload if isinstance(item, dict) and isinstance(item.get("question"), str) and isinstance(item.get("answer"), str)][-self._max_turns:]
        except (OSError, ValueError, TypeError):
            return []

    def _path(self, key: str) -> Path:
        return self._root / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"
