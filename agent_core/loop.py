"""A minimal, model-independent tool-calling agent loop."""

from __future__ import annotations

import json

from .types import AgentResult, ChatModel, Message, Tool


class Agent:
    def __init__(
        self,
        model: ChatModel,
        tools: list[Tool],
        *,
        system_prompt: str = "You are a helpful agent. Use tools when needed, and continue until the task is complete.",
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        self.model = model
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("tool names must be unique")

        self.system_prompt = system_prompt
        self.max_steps = max_steps

    def run(self, prompt: str) -> AgentResult:
        messages: list[Message] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        schemas = [tool.schema() for tool in self.tools.values()]

        for step in range(1, self.max_steps + 1):
            assistant = self.model.complete(messages, schemas)
            messages.append(assistant)

            tool_calls = assistant.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                return AgentResult(
                    answer=str(assistant.get("content", "")),
                    messages=messages,
                    steps=step,
                )

            for call in tool_calls:
                messages.append(self._execute_tool(call))

        raise RuntimeError(f"agent exceeded max_steps={self.max_steps}")

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
