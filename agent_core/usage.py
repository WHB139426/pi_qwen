"""JSON-backed token usage storage."""

from __future__ import annotations

import json
from pathlib import Path

from .types import TokenUsage, UsageState


class JsonUsageStore:
    """Persist the latest turn and cumulative conversation token usage."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> UsageState:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"usage file does not exist: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"usage file is invalid JSON: {self.path}") from exc

        if not isinstance(data, dict):
            raise RuntimeError("usage JSON must be an object")

        return UsageState(
            turn=self._parse_usage(data.get("turn"), "turn"),
            conversation=self._parse_usage(data.get("conversation"), "conversation"),
            current_context_tokens=self._parse_non_negative_int(
                data.get("current_context_tokens"),
                "current_context_tokens",
            ),
        )

    def save(self, state: UsageState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(
                {
                    "turn": self._usage_dict(state.turn),
                    "conversation": self._usage_dict(state.conversation),
                    "current_context_tokens": state.current_context_tokens,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    @classmethod
    def _parse_usage(cls, value: object, name: str) -> TokenUsage:
        if not isinstance(value, dict):
            raise RuntimeError(f"usage JSON field '{name}' must be an object")
        return TokenUsage(
            input_tokens=cls._parse_non_negative_int(
                value.get("input_tokens"),
                f"{name}.input_tokens",
            ),
            output_tokens=cls._parse_non_negative_int(
                value.get("output_tokens"),
                f"{name}.output_tokens",
            ),
        )

    @staticmethod
    def _parse_non_negative_int(value: object, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(f"usage JSON field '{name}' must be a non-negative integer")
        return value

    @staticmethod
    def _usage_dict(usage: TokenUsage) -> dict[str, int]:
        return {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
