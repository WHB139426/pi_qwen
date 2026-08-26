"""Transformers adapter for the local Qwen3.8-27B checkpoint."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from agent_core.types import Message


TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>\s*(.*?)\s*</function>\s*</tool_call>",
    re.DOTALL,
)
PARAMETER_PATTERN = re.compile(r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", re.DOTALL)


@dataclass(frozen=True)
class GenerationOptions:
    max_new_tokens: int = 32*1024
    enable_thinking: bool = True
    reasoning_effort: str = "medium"
    do_sample: bool = True
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20


class QwenModel:
    def __init__(
        self,
        model_path: str,
        *,
        options: GenerationOptions | None = None,
        device_map: str = "auto",
        show_raw_trace: bool = False,
    ) -> None:
        import torch
        from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

        self.torch = torch
        self.options = options or GenerationOptions()
        self.show_raw_trace = show_raw_trace
        self._traced_ids: list[int] = []
        self._trace_turn = 0
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = Qwen3_5ForConditionalGeneration.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map=device_map,
            attn_implementation="flash_attention_3",
        ).eval()
        self.input_device = next(self.model.parameters()).device

    def complete(self, messages: list[Message], tools: list[dict[str, object]]) -> Message:
        inputs = self.processor.apply_chat_template(
            messages,
            tools=tools,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=self.options.enable_thinking,
            reasoning_effort=self.options.reasoning_effort,
            preserve_thinking=True,
        ).to(self.input_device)

        generate_options: dict[str, object] = {
            "max_new_tokens": self.options.max_new_tokens,
            "do_sample": self.options.do_sample,
        }
        if self.options.do_sample:
            generate_options.update(
                temperature=self.options.temperature,
                top_p=self.options.top_p,
                top_k=self.options.top_k,
            )

        with self.torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generate_options)

        new_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        if self.show_raw_trace:
            current_input_ids = inputs["input_ids"][0].tolist()
            current_output_ids = output_ids[0].tolist()

            if len(messages) <= 2:
                self._traced_ids = []
                self._trace_turn = 0

            prefix_length = _common_prefix_length(self._traced_ids, current_input_ids)
            incremental_ids = current_input_ids[prefix_length:] + new_ids[0].tolist()
            self._trace_turn += 1

            raw_trace = self.processor.decode(
                incremental_ids,
                skip_special_tokens=False,
            )
            _print_raw(
                f"AGENT TRACE · TURN {self._trace_turn}",
                _annotate_trace(raw_trace, self._trace_turn),
            )
            self._traced_ids = current_output_ids

        text = self.processor.batch_decode(new_ids, skip_special_tokens=True)[0]
        return parse_assistant_message(text, expect_thinking=self.options.enable_thinking)


def parse_assistant_message(text: str, *, expect_thinking: bool = False) -> Message:
    reasoning, content = _split_thinking(text, expect_thinking)
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


def _print_raw(label: str, text: str) -> None:
    border = f"{'=' * 24} {label} {'=' * 24}"
    print(f"\n{border}\n{text}\n{'=' * len(border)}\n", flush=True)


def _common_prefix_length(left: list[int], right: list[int]) -> int:
    length = 0
    for left_id, right_id in zip(left, right):
        if left_id != right_id:
            break
        length += 1
    return length


def _annotate_trace(text: str, turn: int) -> str:
    """Add readable role labels without removing or rewriting model tokens."""

    def add_label(match: re.Match[str]) -> str:
        role = match.group(1)
        if role == "system":
            label = "SYSTEM PROMPT"
        elif role == "assistant":
            label = f"MODEL OUTPUT · TURN {turn}"
        elif text.startswith("<tool_response>", match.end()):
            label = f"TOOL RESULT · TURN {turn}"
        else:
            label = f"USER INPUT · TURN {turn}"
        return f"\n-------------------- {label} --------------------\n{match.group(0)}"

    return re.sub(r"<\|im_start\|>(system|user|assistant)\n", add_label, text).lstrip()
