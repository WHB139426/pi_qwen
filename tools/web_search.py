"""DuckDuckGo web search tool."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from agent_core import Tool


def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web with DuckDuckGo and return titles, URLs, and snippets."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be between 1 and 10")

    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; MinimalQwenAgent/1.0)"},
        follow_redirects=True,
        timeout=15.0,
    )
    response.raise_for_status()

    parser = _DuckDuckGoParser(max_results)
    parser.feed(response.text)
    parser.close()
    return parser.results


class _DuckDuckGoParser(HTMLParser):
    """Extract DuckDuckGo result cards from its HTML search page."""

    def __init__(self, max_results: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_results = max_results
        self.results: list[dict[str, str]] = []
        self._result: dict[str, str] | None = None
        self._capture: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._finish_result()
            self._result = {
                "title": "",
                "url": _unwrap_duckduckgo_url(attributes.get("href") or ""),
                "snippet": "",
            }
            self._capture = "title"
            self._text = []
        elif self._result is not None and "result__snippet" in classes:
            self._capture = "snippet"
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            self._store_text("title")
        elif self._capture == "snippet" and tag in {"a", "div"}:
            self._store_text("snippet")
            self._finish_result()

    def close(self) -> None:
        super().close()
        self._finish_result()

    def _store_text(self, field: str) -> None:
        if self._result is not None:
            self._result[field] = " ".join("".join(self._text).split())
        self._capture = None
        self._text = []

    def _finish_result(self) -> None:
        if (
            self._result is not None
            and self._result["title"]
            and self._result["url"]
            and len(self.results) < self.max_results
        ):
            self.results.append(self._result)
        self._result = None
        self._capture = None
        self._text = []


def _unwrap_duckduckgo_url(url: str) -> str:
    absolute_url = urljoin("https://duckduckgo.com", url)
    parsed = urlparse(absolute_url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return absolute_url


WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The web search query.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return.",
            "minimum": 1,
            "maximum": 10,
            "default": 5,
        },
    },
    "required": ["query"],
}


WEB_SEARCH_TOOL = Tool(
    "web_search",
    "Search the web for current information using DuckDuckGo.",
    WEB_SEARCH_SCHEMA,
    web_search,
)
