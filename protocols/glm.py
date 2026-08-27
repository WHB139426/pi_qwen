"""GLM chat-template rendering and assistant-output parsing."""

from __future__ import annotations

import json
import re
import uuid

from agent_core.types import Message


TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*([^<\s]+)\s*(.*?)\s*</tool_call>",
    re.DOTALL,
)
ARGUMENT_PATTERN = re.compile(
    r"<arg_key>\s*(.*?)\s*</arg_key>\s*"
    r"<arg_value>\s*(.*?)\s*</arg_value>",
    re.DOTALL,
)
STOP_TOKEN_PATTERN = re.compile(
    r"(?:(?:<\|endoftext\|>|<\|user\|>|<\|observation\|>)\s*)+$"
)


class GLMProtocol:
    """Own the GLM context format independently of an inference backend."""

    def __init__(
        self,
        model_path: str,
        *,
        reasoning_effort: str = "max",
        preserve_thinking: bool = True,
    ) -> None:
        from transformers import AutoTokenizer

        if reasoning_effort not in {"low", "high", "max"}:
            raise ValueError("GLM reasoning_effort must be 'low', 'high', or 'max'")

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.reasoning_effort = reasoning_effort
        self.preserve_thinking = preserve_thinking

    def render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
    ) -> str:
        rendered = self.tokenizer.apply_chat_template(
            messages,
            tools=tools,
            tokenize=False,
            add_generation_prompt=True,
            reasoning_effort=self.reasoning_effort,
            clear_thinking=not self.preserve_thinking,
        )
        if not isinstance(rendered, str):
            raise TypeError("chat template did not return text")
        return rendered

    def parse(self, text: str) -> Message:
        text = STOP_TOKEN_PATTERN.sub("", text).strip()
        reasoning, content = _split_thinking(text)
        tool_calls = []

        for match in TOOL_CALL_PATTERN.finditer(content):
            name = match.group(1).strip()
            arguments = {
                argument.group(1).strip(): _parse_value(argument.group(2).strip())
                for argument in ARGUMENT_PATTERN.finditer(match.group(2))
            }
            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex}",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )

        message: Message = {
            "role": "assistant",
            "content": TOOL_CALL_PATTERN.sub("", content).strip(),
        }
        if reasoning:
            message["reasoning_content"] = reasoning
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message


def _split_thinking(text: str) -> tuple[str, str]:
    if "</think>" not in text:
        raise RuntimeError("generation ended before the closing </think> tag")
    reasoning, _, content = text.partition("</think>")
    return reasoning.removeprefix("<think>").strip(), content.strip()


def _parse_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
