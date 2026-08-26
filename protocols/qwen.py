"""Qwen chat-template rendering and assistant-output parsing."""

from __future__ import annotations

import json
import re
import uuid

from agent_core.types import Message


TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>\s*(.*?)\s*</function>\s*</tool_call>",
    re.DOTALL,
)
PARAMETER_PATTERN = re.compile(r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", re.DOTALL)
IM_END_PATTERN = re.compile(r"(?:<\|im_end\|>\s*)+$")


class QwenProtocol:
    """Own the Qwen context format independently of an inference backend."""

    def __init__(
        self,
        model_path: str,
        *,
        enable_thinking: bool = True,
        reasoning_effort: str = "medium",
        preserve_thinking: bool = True,
    ) -> None:
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.enable_thinking = enable_thinking
        self.reasoning_effort = reasoning_effort
        self.preserve_thinking = preserve_thinking

    def render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        *,
        add_generation_prompt: bool = True,
    ) -> str:
        rendered = self.tokenizer.apply_chat_template(
            messages,
            tools=tools,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=self.enable_thinking,
            reasoning_effort=self.reasoning_effort,
            preserve_thinking=self.preserve_thinking,
        )
        if not isinstance(rendered, str):
            raise TypeError("chat template did not return text")
        return rendered

    def parse(self, text: str) -> Message:
        text = IM_END_PATTERN.sub("", text).strip()
        reasoning, content = _split_thinking(text, self.enable_thinking)
        tool_calls = []

        for match in TOOL_CALL_PATTERN.finditer(content):
            name = match.group(1).strip()
            arguments = {
                parameter.group(1).strip(): _parse_value(parameter.group(2).strip())
                for parameter in PARAMETER_PATTERN.finditer(match.group(2))
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


def _split_thinking(text: str, expect_thinking: bool) -> tuple[str, str]:
    if "</think>" in text:
        reasoning, _, content = text.partition("</think>")
        return reasoning.removeprefix("<think>").strip(), content.strip()
    if expect_thinking:
        raise RuntimeError("generation ended before the closing </think> tag")
    return "", text.strip()


def _parse_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
