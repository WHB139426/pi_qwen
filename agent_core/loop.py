"""A minimal, model-independent tool-calling agent loop."""

from __future__ import annotations

import json
from pathlib import Path

from .conversation import JsonConversationStore
from .types import (
    AgentEventCallback,
    AgentResult,
    ChatProtocol,
    Message,
    ModelInput,
    TextGenerator,
    TokenUsage,
    Tool,
    ToolOutput,
    UsageState,
)
from .usage import JsonUsageStore


class Agent:
    def __init__(
        self,
        model: TextGenerator,
        tools: list[Tool],
        *,
        protocol: ChatProtocol,
        system_prompt: str = "You are a helpful agent. Use tools when needed, and continue until the task is complete.",
        max_steps: int = 8,
        conversation_store: JsonConversationStore | None = None,
        usage_store: JsonUsageStore | None = None,
        trace_path: str | Path | None = None,
        event_callback: AgentEventCallback | None = None,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        self.model = model
        self.protocol = protocol
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("tool names must be unique")

        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.conversation_store = conversation_store
        self.usage_store = usage_store
        self.trace_path = Path(trace_path) if trace_path is not None else None
        self.event_callback = event_callback
        self._messages: list[Message] | None = None
        self._usage_state = UsageState()

    def run(self, prompt: str) -> AgentResult:
        messages = self._load_or_initialize_messages()
        messages.append({"role": "user", "content": prompt})
        self._save_messages(messages)

        schemas = [tool.schema() for tool in self.tools.values()]
        usage = TokenUsage()
        previous_usage_state = self._load_usage_state()
        conversation_usage = previous_usage_state.conversation
        self._save_usage_state(
            UsageState(
                turn=usage,
                conversation=conversation_usage,
                current_context_tokens=previous_usage_state.current_context_tokens,
            )
        )
        transient_messages: list[Message] = []

        for step in range(1, self.max_steps + 1):
            messages = self._load_messages(messages)
            render_messages = [*messages, *transient_messages]
            transient_messages = []
            model_input = self.protocol.render(render_messages, schemas)
            context = (
                model_input.context
                if isinstance(model_input, ModelInput)
                else model_input
            )
            self._emit({"type": "generation_start", "step": step})
            generation = self.model.generate(
                model_input,
                on_delta=lambda delta: self._emit(
                    {"type": "model_delta", "step": step, "delta": delta}
                ),
            )
            raw_output = generation.text
            usage = usage + generation.usage
            conversation_usage = conversation_usage + generation.usage
            self._save_usage_state(
                UsageState(
                    turn=usage,
                    conversation=conversation_usage,
                    current_context_tokens=generation.usage.total_tokens,
                )
            )
            self._write_trace(context, raw_output)
            assistant = self.protocol.parse(raw_output)
            self._emit(
                {
                    "type": "assistant_message",
                    "step": step,
                    "content": assistant.get("content", ""),
                    "reasoning_content": assistant.get("reasoning_content", ""),
                }
            )
            messages.append(assistant)
            self._save_messages(messages)

            tool_calls = assistant.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                answer = str(assistant.get("content", ""))
                self._emit({"type": "final_answer", "step": step, "content": answer})
                return AgentResult(
                    answer=answer,
                    messages=messages,
                    steps=step,
                    usage=usage,
                    conversation_usage=conversation_usage,
                    current_context_tokens=generation.usage.total_tokens,
                )

            for call in tool_calls:
                self._emit_tool_call(step, call)
                tool_result, tool_transient_messages = self._execute_tool(call)
                messages.append(tool_result)
                self._save_messages(messages)
                transient_messages.extend(tool_transient_messages)
                self._emit(
                    {
                        "type": "tool_result",
                        "step": step,
                        "tool_call_id": tool_result.get("tool_call_id", ""),
                        "name": tool_result.get("name", ""),
                        "content": tool_result.get("content", ""),
                    }
                )

        raise RuntimeError(f"agent exceeded max_steps={self.max_steps}")

    def reset(self) -> None:
        if self.conversation_store is not None:
            self.conversation_store.clear()
        if self.usage_store is not None:
            self.usage_store.clear()
        self._save_messages(self._initial_messages())
        self._save_usage_state(UsageState())

    def _load_or_initialize_messages(self) -> list[Message]:
        if self.conversation_store is not None and self.conversation_store.exists():
            return self.conversation_store.load()
        if self._messages is not None:
            return self._messages
        return self._initial_messages()

    def _initial_messages(self) -> list[Message]:
        if not self.system_prompt:
            return []
        return [{"role": "system", "content": self.system_prompt}]

    def _load_messages(self, in_memory_messages: list[Message]) -> list[Message]:
        if self.conversation_store is None:
            return in_memory_messages
        return self.conversation_store.load()

    def _save_messages(self, messages: list[Message]) -> None:
        self._messages = messages
        if self.conversation_store is None:
            return
        self.conversation_store.save(messages)

    def _load_usage_state(self) -> UsageState:
        if self.usage_store is not None and self.usage_store.exists():
            return self.usage_store.load()
        return self._usage_state

    def _save_usage_state(self, state: UsageState) -> None:
        self._usage_state = state
        if self.usage_store is not None:
            self.usage_store.save(state)

    def _write_trace(self, context: str, raw_output: str) -> None:
        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text(context + raw_output, encoding="utf-8")

    def _emit(self, event: dict[str, object]) -> None:
        if self.event_callback is None:
            return
        try:
            self.event_callback(event)
        except Exception:
            pass

    def _emit_tool_call(self, step: int, call: object) -> None:
        if not isinstance(call, dict):
            return
        function = call.get("function")
        if not isinstance(function, dict):
            return
        self._emit(
            {
                "type": "tool_call",
                "step": step,
                "tool_call_id": call.get("id", ""),
                "name": function.get("name", ""),
                "arguments": function.get("arguments", {}),
            }
        )

    def _execute_tool(self, call: object) -> tuple[Message, list[Message]]:
        if not isinstance(call, dict):
            return self._tool_result("", "", error="invalid tool call"), []

        call_id = str(call.get("id", ""))
        function = call.get("function")
        if not isinstance(function, dict):
            return self._tool_result(call_id, "", error="tool call has no function"), []

        name = str(function.get("name", ""))
        arguments = function.get("arguments", {})
        if not isinstance(arguments, dict):
            return self._tool_result(call_id, name, error="tool arguments must be an object"), []

        tool = self.tools.get(name)
        if tool is None:
            return self._tool_result(call_id, name, error=f"unknown tool: {name}"), []

        try:
            value = tool.function(**arguments)
            if isinstance(value, ToolOutput):
                return (
                    self._tool_result(call_id, name, value=value.value),
                    list(value.transient_messages),
                )
            return self._tool_result(call_id, name, value=value), []
        except Exception as exc:
            return (
                self._tool_result(call_id, name, error=f"{type(exc).__name__}: {exc}"),
                [],
            )

    @staticmethod
    def _tool_result(call_id: str, name: str, *, value: object = None, error: str | None = None) -> Message:
        payload = {"ok": error is None, "result": value} if error is None else {"ok": False, "error": error}
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": json.dumps(payload, ensure_ascii=False, default=str),
        }
