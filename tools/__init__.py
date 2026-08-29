"""Tool registry for the example agent."""

from .coding import BASH_TOOL, EDIT_TOOL, READ_TOOL, WRITE_TOOL
from .skill import SKILL_TOOL
from .view_image import make_view_image_tool
from .web_search import WEB_SEARCH_TOOL


TOOLS = [
    READ_TOOL,
    BASH_TOOL,
    EDIT_TOOL,
    WRITE_TOOL,
    WEB_SEARCH_TOOL,
    SKILL_TOOL,
]

__all__ = ["TOOLS", "make_view_image_tool"]
