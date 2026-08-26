"""Minimal filesystem and shell tools for coding tasks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent_core import Tool


MAX_OUTPUT_BYTES = 50 * 1024
DEFAULT_READ_LINES = 2_000


def read(path: str, offset: int = 1, limit: int = DEFAULT_READ_LINES) -> dict[str, object]:
    """Read a UTF-8 text file, optionally selecting a range of lines."""
    if offset < 1:
        raise ValueError("offset must be at least 1")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    file_path = _path(path)
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return {
            "path": str(file_path),
            "content": "",
            "start_line": 0,
            "end_line": 0,
            "total_lines": 0,
            "truncated": False,
        }
    if offset > total_lines:
        raise ValueError(f"offset {offset} is beyond the end of the file ({total_lines} lines)")

    selected = lines[offset - 1 : offset - 1 + limit]
    text, byte_truncated = _truncate("\n".join(selected))
    end_line = offset + len(selected) - 1
    return {
        "path": str(file_path),
        "content": text,
        "start_line": offset,
        "end_line": end_line,
        "total_lines": total_lines,
        "truncated": byte_truncated or end_line < total_lines,
    }


def bash(command: str, timeout: float | None = None) -> dict[str, object]:
    """Execute a Bash command in the current working directory."""
    if not command.strip():
        raise ValueError("command must not be empty")
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    try:
        completed = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"command timed out after {timeout} seconds") from exc

    stdout, stdout_truncated = _truncate(completed.stdout)
    stderr, stderr_truncated = _truncate(completed.stderr)
    return {
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": stdout_truncated or stderr_truncated,
    }


def edit(path: str, old_text: str, new_text: str) -> dict[str, object]:
    """Replace one uniquely matching text block in a UTF-8 file."""
    if not old_text:
        raise ValueError("old_text must not be empty")

    file_path = _path(path)
    content = file_path.read_text(encoding="utf-8")
    matches = content.count(old_text)
    if matches == 0:
        raise ValueError("old_text was not found in the file")
    if matches > 1:
        raise ValueError(f"old_text matched {matches} locations; provide a unique block")

    updated = content.replace(old_text, new_text, 1)
    file_path.write_text(updated, encoding="utf-8")
    return {
        "path": str(file_path),
        "replacements": 1,
        "bytes_written": len(updated.encode("utf-8")),
    }


def write(path: str, content: str) -> dict[str, object]:
    """Create or overwrite a UTF-8 text file."""
    file_path = _path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return {
        "path": str(file_path),
        "bytes_written": len(content.encode("utf-8")),
    }


def _path(path: str) -> Path:
    if not path.strip():
        raise ValueError("path must not be empty")
    return Path(path).expanduser()


def _truncate(text: str) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text, False
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore"), True


READ_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the UTF-8 text file to read."},
        "offset": {
            "type": "integer",
            "description": "One-indexed line number to start reading from.",
            "minimum": 1,
            "default": 1,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of lines to return.",
            "minimum": 1,
            "default": DEFAULT_READ_LINES,
        },
    },
    "required": ["path"],
}

BASH_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Bash command to execute."},
        "timeout": {
            "type": "number",
            "description": "Optional timeout in seconds.",
            "exclusiveMinimum": 0,
        },
    },
    "required": ["command"],
}

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the UTF-8 text file to edit."},
        "old_text": {"type": "string", "description": "Exact, uniquely matching text to replace."},
        "new_text": {"type": "string", "description": "Replacement text."},
    },
    "required": ["path", "old_text", "new_text"],
}

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the file to create or overwrite."},
        "content": {"type": "string", "description": "Complete UTF-8 content to write."},
    },
    "required": ["path", "content"],
}


READ_TOOL = Tool(
    "read",
    "Read a UTF-8 text file with optional line offset and limit.",
    READ_SCHEMA,
    read,
)
BASH_TOOL = Tool(
    "bash",
    "Execute a Bash command in the current working directory and return its exit code and output.",
    BASH_SCHEMA,
    bash,
)
EDIT_TOOL = Tool(
    "edit",
    "Edit a UTF-8 text file by replacing one exact, uniquely matching text block.",
    EDIT_SCHEMA,
    edit,
)
WRITE_TOOL = Tool(
    "write",
    "Create or completely overwrite a UTF-8 text file, creating parent directories when needed.",
    WRITE_SCHEMA,
    write,
)
