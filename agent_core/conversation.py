"""JSON-backed conversation storage."""

from __future__ import annotations

import json
from pathlib import Path

from .types import Message


class JsonConversationStore:
    """Persist the complete message history in one JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[Message]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"conversation file does not exist: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"conversation file is invalid JSON: {self.path}") from exc

        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise RuntimeError("conversation JSON must be a list of message objects")
        return data

    def save(self, messages: list[Message]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
