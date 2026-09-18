"""DeepSeek-V4.1 prompt rendering and DSML tool-call parsing."""

from __future__ import annotations

import importlib.util
import json
import re
import uuid
from pathlib import Path
from types import ModuleType

from agent_core.types import Message, ModelInput


TOOL_CALLS_PATTERN = re.compile(
    r"<｜DSML｜ calls>\s*(.*?)\s*</｜DSML｜ calls>",
    re.DOTALL,
)
TOOL_CALL_PATTERN = re.compile(
    r'<｜DSML｜ invoke name="([^"]+)">\s*(.*?)\s*</｜DSML｜ invoke>',
    re.DOTALL,
)
PARAMETER_PATTERN = re.compile(
    r'<｜DSML｜ parameter name="([^"]+)" string="(true|false)">'
    r"(.*?)</｜DSML｜ parameter>",
    re.DOTALL,
)
STOP_TOKEN_PATTERN = re.compile(r"(?:<｜end▁of▁sentence｜>\s*)+$")


class DeepSeekProtocol:
    """Construct DeepSeek-V4.1 contexts without delegating that work to vLLM."""

    def __init__(
        self,
        model_path: str,
        *,
        reasoning_effort: int | str = 100,
        preserve_thinking: bool = True,
    ) -> None:
        if not (
            isinstance(reasoning_effort, int)
            and not isinstance(reasoning_effort, bool)
            and 1 <= reasoning_effort <= 100
        ) and reasoning_effort not in {"low", "high", "max"}:
            raise ValueError(
                "DeepSeek reasoning_effort must be an integer from 1 to 100 "
                "or 'low', 'high', or 'max'"
            )

        self.reasoning_effort = reasoning_effort
        self.preserve_thinking = preserve_thinking
        self.encoding = _load_reference_encoding(Path(model_path))

    def render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
    ) -> str | ModelInput:
        if _contains_videos(messages):
            raise ValueError(
                "DeepSeek-V4.1-Flash accepts image inputs but not video inputs"
            )

        prepared = _prepare_encoding_messages(messages, tools)
        rendered = self.encoding.encode_messages(
            prepared,
            thinking_mode="thinking",
            reasoning_effort=self.reasoning_effort,
            drop_thinking=not self.preserve_thinking,
        )
        if not isinstance(rendered, str):
            raise TypeError("DeepSeek reference encoder did not return text")

        if _contains_images(messages):
            return ModelInput(
                context=rendered,
                api_messages=_prepare_api_messages(messages),
                tools=tools,
                chat_template_kwargs={
                    "thinking_mode": "thinking",
                    "reasoning_effort": self.reasoning_effort,
                },
            )
        return rendered

    def parse(self, text: str) -> Message:
        text = STOP_TOKEN_PATTERN.sub("", text).strip()
        if "</think>" not in text:
            raise RuntimeError(
                "DeepSeek response is missing the closing </think> tag"
            )

        reasoning, _, content = text.partition("</think>")
        reasoning = reasoning.removeprefix("<think>").strip()
        tool_calls: list[dict[str, object]] = []

        for block in TOOL_CALLS_PATTERN.finditer(content):
            for call in TOOL_CALL_PATTERN.finditer(block.group(1)):
                arguments: dict[str, object] = {}
                for parameter in PARAMETER_PATTERN.finditer(call.group(2)):
                    name, is_string, value = parameter.groups()
                    arguments[name] = (
                        value if is_string == "true" else _parse_value(value)
                    )
                tool_calls.append(
                    {
                        "id": f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": call.group(1),
                            "arguments": arguments,
                        },
                    }
                )

        message: Message = {
            "role": "assistant",
            "content": TOOL_CALLS_PATTERN.sub("", content).strip(),
        }
        if reasoning:
            message["reasoning_content"] = reasoning
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message


def _load_reference_encoding(model_path: Path) -> ModuleType:
    encoding_path = model_path / "encoding" / "encoding.py"
    if not encoding_path.is_file():
        raise FileNotFoundError(
            "DeepSeek-V4.1 reference encoder was not found at "
            f"{encoding_path}. Use the complete official model repository."
        )

    spec = importlib.util.spec_from_file_location(
        f"_deepseek_v41_encoding_{abs(hash(encoding_path.resolve()))}",
        encoding_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load DeepSeek encoder from {encoding_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "encode_messages", None)):
        raise ImportError(
            f"DeepSeek encoder at {encoding_path} has no encode_messages()"
        )
    return module


def _prepare_encoding_messages(
    messages: list[Message],
    tools: list[dict[str, object]],
) -> list[Message]:
    prepared = _prepare_messages(messages)
    if not tools:
        return prepared

    if prepared and prepared[0].get("role") == "system":
        prepared[0]["tools"] = tools
    else:
        prepared.insert(0, {"role": "system", "content": "", "tools": tools})
    return prepared


def _prepare_messages(messages: list[Message]) -> list[Message]:
    allowed_keys = {
        "role",
        "content",
        "reasoning_content",
        "tool_calls",
        "tool_call_id",
        "name",
    }
    return [
        {key: value for key, value in message.items() if key in allowed_keys}
        for message in messages
    ]


def _prepare_api_messages(messages: list[Message]) -> list[Message]:
    prepared = _prepare_messages(messages)
    for message in prepared:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
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
        message["tool_calls"] = normalized_calls
    return prepared


def _contains_images(messages: list[Message]) -> bool:
    return _contains_media_types(messages, {"image", "image_url"})


def _contains_videos(messages: list[Message]) -> bool:
    return _contains_media_types(messages, {"video", "video_url"})


def _contains_media_types(messages: list[Message], types: set[str]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") in types:
                return True
    return False


def _parse_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
