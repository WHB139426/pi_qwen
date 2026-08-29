"""Tool for discovering and dynamically loading reusable skills."""

from __future__ import annotations

from pathlib import Path

from agent_core import Tool
from agent_core.skills import SkillRegistry


SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
SKILL_REGISTRY = SkillRegistry(SKILLS_ROOT)


def render_skill_catalog() -> str:
    """Render concise skill metadata for inclusion in the system prompt."""
    skills = SKILL_REGISTRY.list()
    if not skills:
        return "- No specialized skills are currently available."
    return "\n".join(
        f"- `{metadata.name}`: {metadata.description}" for metadata in skills
    )


def skill(name: str) -> object:
    metadata, instructions = SKILL_REGISTRY.load(name)
    return {
        "name": metadata.name,
        "description": metadata.description,
        "instructions": instructions,
    }


SKILL_TOOL = Tool(
    name="skill",
    description=(
        "Load the full instructions for one specialized workflow listed in the "
        "system prompt. Call this before performing a task that matches a skill."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact registered skill name from the system prompt.",
            },
        },
        "required": ["name"],
    },
    function=skill,
)
