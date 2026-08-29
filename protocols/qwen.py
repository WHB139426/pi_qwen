"""Qwen chat-template rendering and assistant-output parsing."""

from __future__ import annotations

import json
import re
import uuid

from agent_core.types import Message, ModelInput


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
    ) -> str | ModelInput:
        template_messages = _prepare_template_messages(messages)
        rendered = self.tokenizer.apply_chat_template(
            template_messages,
            tools=tools,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=self.enable_thinking,
            reasoning_effort=self.reasoning_effort,
            preserve_thinking=self.preserve_thinking,
        )
        if not isinstance(rendered, str):
            raise TypeError("chat template did not return text")
        if _contains_multimodal_content(messages):
            return ModelInput(
                context=rendered,
                api_messages=_prepare_api_messages(messages),
                tools=tools,
                chat_template_kwargs={
                    "enable_thinking": self.enable_thinking,
                    "reasoning_effort": self.reasoning_effort,
                    "preserve_thinking": self.preserve_thinking,
                },
            )
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


def _contains_multimodal_content(messages: list[Message]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"image", "image_url", "video", "video_url"}:
                return True
    return False


def _prepare_template_messages(messages: list[Message]) -> list[Message]:
    """Normalize API-only video_url blocks for Qwen's local Jinja template."""
    allowed_keys = {
        "role",
        "content",
        "reasoning_content",
        "tool_calls",
        "tool_call_id",
        "name",
    }
    prepared: list[Message] = [
        {key: value for key, value in message.items() if key in allowed_keys}
        for message in messages
    ]
    for message in prepared:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        normalized_parts: list[object] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "video_url":
                video_url = part.get("video_url")
                url = video_url.get("url") if isinstance(video_url, dict) else video_url
                normalized_parts.append({"type": "video", "video": url})
            else:
                normalized_parts.append(part)
        message["content"] = normalized_parts
    return prepared


def _prepare_api_messages(messages: list[Message]) -> list[Message]:
    """Remove harness metadata and serialize tool arguments for the chat API."""
    prepared: list[Message] = []
    allowed_keys = {
        "role",
        "content",
        "reasoning_content",
        "tool_calls",
        "tool_call_id",
        "name",
    }
    for message in messages:
        item: Message = {
            key: value for key, value in message.items() if key in allowed_keys
        }
        tool_calls = item.get("tool_calls")
        if isinstance(tool_calls, list):
            normalized_calls: list[object] = []
            for call in tool_calls:
                if not isinstance(call, dict):
                    normalized_calls.append(call)
                    continue
                normalized_call = dict(call)
                function = normalized_call.get("function")
                if isinstance(function, dict):
                    normalized_function = dict(function)
                    arguments = normalized_function.get("arguments")
                    if not isinstance(arguments, str):
                        normalized_function["arguments"] = json.dumps(
                            arguments,
                            ensure_ascii=False,
                        )
                    normalized_call["function"] = normalized_function
                normalized_calls.append(normalized_call)
            item["tool_calls"] = normalized_calls
        prepared.append(item)
    return prepared
