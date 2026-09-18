"""Shared interfaces and data types for the agent core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


Message = dict[str, object]
TokenDeltaCallback = Callable[[str], None]
AgentEventCallback = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class ModelInput:
    """A rendered context plus optional OpenAI-compatible multimodal messages."""

    context: str
    api_messages: list[Message] | None = None
    tools: list[dict[str, object]] | None = None
    chat_template_kwargs: dict[str, object] | None = None
    mm_processor_kwargs: dict[str, object] | None = None

    @property
    def is_multimodal(self) -> bool:
        return self.api_messages is not None


class TextGenerator(Protocol):
    def generate(
        self,
        model_input: str | ModelInput,
        *,
        on_delta: TokenDeltaCallback | None = None,
    ) -> Generation:
        """Generate raw text and usage from a fully constructed context."""


class ChatProtocol(Protocol):
    def render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
    ) -> str | ModelInput:
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
class ToolOutput:
    """A persistent tool value plus messages visible for one generation only."""

    value: object
    transient_messages: tuple[Message, ...] = ()


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_details_available: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
            ("cached_input_tokens", self.cached_input_tokens),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        if not isinstance(self.cache_details_available, bool):
            raise ValueError("cache_details_available must be a boolean")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def uncached_input_tokens(self) -> int:
        return self.input_tokens - self.cached_input_tokens

    @property
    def cache_hit_rate(self) -> float:
        if self.input_tokens == 0:
            return 0.0
        return self.cached_input_tokens / self.input_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=(
                self.cached_input_tokens + other.cached_input_tokens
            ),
            cache_details_available=(
                self.cache_details_available and other.cache_details_available
            ),
        )


@dataclass(frozen=True)
class UsageState:
    turn: TokenUsage = TokenUsage()
    conversation: TokenUsage = TokenUsage()
    current_context_tokens: int = 0


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
    conversation_usage: TokenUsage
    current_context_tokens: int
