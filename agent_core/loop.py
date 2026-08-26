"""A minimal, model-independent tool-calling agent loop."""

from __future__ import annotations

import json
from pathlib import Path

from .conversation import JsonConversationStore
from .types import AgentResult, ChatProtocol, Message, TextGenerator, TokenUsage, Tool


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
        trace_path: str | Path | None = None,
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
        self.trace_path = Path(trace_path) if trace_path is not None else None

    def run(self, prompt: str) -> AgentResult:
        messages: list[Message] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        self._save_messages(messages)

        schemas = [tool.schema() for tool in self.tools.values()]
        usage = TokenUsage()

        for step in range(1, self.max_steps + 1):
            messages = self._load_messages(messages)
            context = self.protocol.render(messages, schemas)
            generation = self.model.generate(context)
            raw_output = generation.text
            usage = usage + generation.usage
            self._write_trace(context, raw_output)
            assistant = self.protocol.parse(raw_output)
            messages.append(assistant)
            self._save_messages(messages)

            tool_calls = assistant.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                return AgentResult(
                    answer=str(assistant.get("content", "")),
                    messages=messages,
                    steps=step,
                    usage=usage,
                    current_context_tokens=generation.usage.total_tokens,
                )

            for call in tool_calls:
                messages.append(self._execute_tool(call))
                self._save_messages(messages)

        raise RuntimeError(f"agent exceeded max_steps={self.max_steps}")

    def _load_messages(self, in_memory_messages: list[Message]) -> list[Message]:
        if self.conversation_store is None:
            return in_memory_messages
        return self.conversation_store.load()

    def _save_messages(self, messages: list[Message]) -> None:
        if self.conversation_store is not None:
            self.conversation_store.save(messages)

    def _write_trace(self, context: str, raw_output: str) -> None:
        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text(context + raw_output, encoding="utf-8")

    def _execute_tool(self, call: object) -> Message:
        if not isinstance(call, dict):
            return self._tool_result("", "", error="invalid tool call")

        call_id = str(call.get("id", ""))
        function = call.get("function")
        if not isinstance(function, dict):
            return self._tool_result(call_id, "", error="tool call has no function")

        name = str(function.get("name", ""))
        arguments = function.get("arguments", {})
        if not isinstance(arguments, dict):
            return self._tool_result(call_id, name, error="tool arguments must be an object")

        tool = self.tools.get(name)
        if tool is None:
            return self._tool_result(call_id, name, error=f"unknown tool: {name}")

        try:
            value = tool.function(**arguments)
            return self._tool_result(call_id, name, value=value)
        except Exception as exc:
            return self._tool_result(call_id, name, error=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _tool_result(call_id: str, name: str, *, value: object = None, error: str | None = None) -> Message:
        payload = {"ok": error is None, "result": value} if error is None else {"ok": False, "error": error}
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": json.dumps(payload, ensure_ascii=False, default=str),
        }
