"""Shared interfaces and data types for the agent core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


Message = dict[str, object]


class TextGenerator(Protocol):
    def generate(self, context: str) -> Generation:
        """Generate raw text and usage from a fully constructed context."""


class ChatProtocol(Protocol):
    def render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
    ) -> str:
        """Render structured messages into the model's text context."""

    def parse(self, text: str) -> Message:
        """Parse raw generated text into one assistant message."""


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
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class Generation:
    text: str
    usage: TokenUsage


@dataclass(frozen=True)
class AgentResult:
    answer: str
    messages: list[Message]
    steps: int
    usage: TokenUsage
    current_context_tokens: int
