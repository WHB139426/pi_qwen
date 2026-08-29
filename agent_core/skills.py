"""Discovery and safe loading for repository-owned agent skills."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock


SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_SKILL_BYTES = 128 * 1024


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "description": self.description}


@dataclass(frozen=True)
class _SkillRecord:
    metadata: SkillMetadata
    path: Path


class SkillRegistry:
    """Discover immediate skill directories and load validated SKILL.md files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self._lock = RLock()
        self._records: dict[str, _SkillRecord] = {}

    def list(self) -> list[SkillMetadata]:
        with self._lock:
            self._refresh()
            return [self._records[name].metadata for name in sorted(self._records)]

    def load(self, name: str) -> tuple[SkillMetadata, str]:
        if SKILL_NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("invalid skill name")
        with self._lock:
            self._refresh()
            record = self._records.get(name)
            if record is None:
                raise KeyError(f"unknown skill: {name}")
            metadata, content = self._read_skill(record.path)
            if metadata.name != name:
                raise RuntimeError(f"skill metadata changed while loading: {name}")
            return metadata, content

    def _refresh(self) -> None:
        if not self.root.is_dir() or self.root.is_symlink():
            raise RuntimeError(f"skill root must be a real directory: {self.root}")

        records: dict[str, _SkillRecord] = {}
        for directory in sorted(self.root.iterdir(), key=lambda path: path.name):
            if not directory.is_dir() or directory.is_symlink():
                continue
            skill_path = directory / "SKILL.md"
            if not skill_path.is_file() or skill_path.is_symlink():
                continue
            metadata, _ = self._read_skill(skill_path)
            if metadata.name != directory.name:
                raise ValueError(
                    f"skill name must match its directory: {directory.name}"
                )
            if metadata.name in records:
                raise ValueError(f"duplicate skill name: {metadata.name}")
            records[metadata.name] = _SkillRecord(metadata, skill_path)
        self._records = records

    def _read_skill(self, path: Path) -> tuple[SkillMetadata, str]:
        resolved = path.resolve()
        if path.is_symlink() or self.root not in resolved.parents:
            raise ValueError("skill file must be a real file inside the skill root")
        path = resolved
        size = path.stat().st_size
        if size > MAX_SKILL_BYTES:
            raise ValueError(f"skill exceeds {MAX_SKILL_BYTES} bytes: {path.name}")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"skill must be UTF-8: {path.name}") from exc
        fields = _parse_frontmatter(content)
        name = fields.get("name", "")
        description = fields.get("description", "")
        if SKILL_NAME_PATTERN.fullmatch(name) is None:
            raise ValueError(f"invalid skill name in {path.name}")
        if not description or len(description) > 512:
            raise ValueError(
                f"skill description must contain 1-512 characters: {name}"
            )
        return SkillMetadata(name=name, description=description), content


def _parse_frontmatter(content: str) -> dict[str, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    try:
        end = next(
            index for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid SKILL.md frontmatter line: {line}")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields
