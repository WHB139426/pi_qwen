"""Tool registry for the example agent."""

from .coding import BASH_TOOL, EDIT_TOOL, READ_TOOL, WRITE_TOOL
from .web_search import WEB_SEARCH_TOOL


TOOLS = [
    READ_TOOL,
    BASH_TOOL,
    EDIT_TOOL,
    WRITE_TOOL,
    WEB_SEARCH_TOOL,
]

__all__ = ["TOOLS"]
