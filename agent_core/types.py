"""Shared interfaces and data types for the agent core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


Message = dict[str, object]


class ChatModel(Protocol):
    def complete(self, messages: list[Message], tools: list[dict[str, object]]) -> Message:
        """Return one assistant message."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, object]
    function: Callable[..., object]

    def schema(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True)
class AgentResult:
    answer: str
    messages: list[Message]
    steps: int
