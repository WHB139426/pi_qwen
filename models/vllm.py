"""vLLM OpenAI-compatible model adapter."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from agent_core.types import Message


@dataclass(frozen=True)
class VLLMOptions:
    max_tokens: int = 32 * 1024
    enable_thinking: bool = True
    reasoning_effort: str = "medium"
    do_sample: bool = True
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20


class VLLMModel:
    """Call a model served by vLLM through its OpenAI-compatible API."""

    def __init__(
        self,
        model: str,
        *,
        served_model_name: str | None = None,
        base_url: str = "http://127.0.0.1:8000/v1",
        options: VLLMOptions | None = None,
        show_trace: bool = False,
    ) -> None:
        from openai import OpenAI

        self.model = model
        self.served_model_name = served_model_name or model
        self.options = options or VLLMOptions()
        self.show_trace = show_trace
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")
        self._trace_turn = 0
        self._traced_text = ""
        self.processor = None
        if show_trace:
            from transformers import AutoProcessor

            self.processor = AutoProcessor.from_pretrained(model)

    def complete(self, messages: list[Message], tools: list[dict[str, object]]) -> Message:
        api_messages = _prepare_api_messages(messages)
        temperature = self.options.temperature if self.options.do_sample else 0.0

        response = self.client.chat.completions.create(
            model=self.served_model_name,
            messages=api_messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=self.options.max_tokens,
            temperature=temperature,
            top_p=self.options.top_p,
            extra_body={
                "top_k": self.options.top_k,
                "chat_template_kwargs": {
                    "enable_thinking": self.options.enable_thinking,
                    "reasoning_effort": self.options.reasoning_effort,
                    "preserve_thinking": True,
                },
            },
        )

        raw_message = response.choices[0].message.model_dump(exclude_none=True)
        assistant = _prepare_assistant_message(raw_message)

        if self.show_trace:
            self._print_trace(messages, tools, assistant)

        return assistant

    def _print_trace(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        assistant: Message,
    ) -> None:
        if len(messages) <= 2:
            self._trace_turn = 0
            self._traced_text = ""

        self._trace_turn += 1
        rendered_input = self._render(messages, tools, add_generation_prompt=True)
        rendered_turn = self._render(
            [*messages, assistant],
            tools,
            add_generation_prompt=False,
        )
        input_start = _common_prefix_length(self._traced_text, rendered_input)
        output_start = _common_prefix_length(rendered_input, rendered_turn)
        new_input = rendered_input[input_start:]
        new_output = rendered_turn[output_start:]
        title = f"VLLM TRACE · TURN {self._trace_turn}"
        border = f"{'=' * 24} {title} {'=' * 24}"

        print(f"\n{border}")
        print("-------------------- MODEL INPUT · RENDERED TEXT --------------------")
        print(new_input)
        print("-------------------- MODEL OUTPUT · RENDERED TEXT --------------------")
        print(new_output)
        print("=" * len(border), flush=True)

        self._traced_text = rendered_turn

    def _render(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        *,
        add_generation_prompt: bool,
    ) -> str:
        if self.processor is None:
            raise RuntimeError("trace processor is not initialized")

        rendered = self.processor.apply_chat_template(
            messages,
            tools=tools,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=self.options.enable_thinking,
            reasoning_effort=self.options.reasoning_effort,
            preserve_thinking=True,
        )
        if not isinstance(rendered, str):
            raise TypeError("chat template did not return text")
        return rendered


def _prepare_api_messages(messages: list[Message]) -> list[Message]:
    """Convert internal tool arguments to the JSON strings required by the API."""

    prepared = copy.deepcopy(messages)
    for message in prepared:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict):
                continue
            arguments = function.get("arguments")
            if isinstance(arguments, dict):
                function["arguments"] = json.dumps(arguments, ensure_ascii=False)

    return prepared


def _prepare_assistant_message(raw: dict[str, object]) -> Message:
    """Convert an OpenAI response message into the Agent's internal format."""

    assistant: Message = {
        "role": "assistant",
        "content": raw.get("content") or "",
    }

    reasoning = raw.get("reasoning") or raw.get("reasoning_content")
    if reasoning:
        assistant["reasoning_content"] = reasoning

    raw_calls = raw.get("tool_calls")
    if not isinstance(raw_calls, list):
        return assistant

    tool_calls = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function")
        if not isinstance(function, dict):
            continue

        arguments = function.get("arguments", "{}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        tool_calls.append(
            {
                "id": str(call.get("id", "")),
                "type": "function",
                "function": {
                    "name": str(function.get("name", "")),
                    "arguments": arguments,
                },
            }
        )

    if tool_calls:
        assistant["tool_calls"] = tool_calls
    return assistant


def _common_prefix_length(left: str, right: str) -> int:
    length = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        length += 1
    return length
