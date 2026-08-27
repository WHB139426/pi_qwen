"""Minimal password-protected web entry point for the agent harness."""

from __future__ import annotations

import hmac
import html
import os
import secrets
import traceback
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import bleach
import markdown

from agent_core import JsonConversationStore, JsonUsageStore, Message, UsageState
from main import CONTEXT_WINDOW, create_agent


HOST = "127.0.0.1"
PORT = 8765
USERNAME = "haibo"
SESSION_COOKIE_NAME = "haibo_agent_session"
MAX_PROMPT_CHARS = 20_000
MAX_REQUEST_BYTES = 64 * 1024
DEFAULT_REASONING_EFFORT = "max"
REASONING_EFFORTS = ("low", "high", "max")
CONVERSATIONS_ROOT = Path("./tmp/conversations")
CONVERSATION_LOCKS: dict[str, Lock] = {}
CONVERSATION_LOCKS_GUARD = Lock()
MARKDOWN_EXTENSIONS = ["fenced_code", "sane_lists", "tables"]
MARKDOWN_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "br",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "p",
    "pre",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
}
MARKDOWN_ATTRIBUTES = {
    "a": ["href", "title"],
    "code": ["class"],
}


def validate_conversation_id(conversation_id: str) -> str:
    try:
        parsed = UUID(conversation_id)
    except ValueError as exc:
        raise ValueError("invalid conversation id") from exc
    if str(parsed) != conversation_id:
        raise ValueError("invalid conversation id")
    return conversation_id


def conversation_paths(conversation_id: str) -> tuple[Path, Path, Path]:
    conversation_id = validate_conversation_id(conversation_id)
    directory = CONVERSATIONS_ROOT / conversation_id
    return (
        directory / "conversation.json",
        directory / "usage.json",
        directory / "trace.txt",
    )


def conversation_lock(conversation_id: str) -> Lock:
    conversation_id = validate_conversation_id(conversation_id)
    with CONVERSATION_LOCKS_GUARD:
        return CONVERSATION_LOCKS.setdefault(conversation_id, Lock())


def load_messages(conversation_id: str) -> list[Message]:
    conversation_path, _, _ = conversation_paths(conversation_id)
    store = JsonConversationStore(conversation_path)
    if not store.exists():
        return []
    return store.load()


def load_usage_state(conversation_id: str) -> UsageState:
    _, usage_path, _ = conversation_paths(conversation_id)
    store = JsonUsageStore(usage_path)
    if not store.exists():
        return UsageState()
    return store.load()


def render_markdown(content: str) -> str:
    rendered = markdown.markdown(content, extensions=MARKDOWN_EXTENSIONS)
    return bleach.clean(
        rendered,
        tags=MARKDOWN_TAGS,
        attributes=MARKDOWN_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )


def render_history(messages: list[Message]) -> str:
    rendered = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content:
            continue
        body = (
            f"<pre>{html.escape(content)}</pre>"
            if role == "user"
            else f'<div class="markdown-body">{render_markdown(content)}</div>'
        )
        label = "You" if role == "user" else "Assistant"
        rendered.append(f'<section class="message {role}" aria-label="{label}">{body}</section>')
    if not rendered:
        return '<p class="empty">No messages yet.</p>'
    return "".join(rendered)


def has_visible_messages(messages: list[Message]) -> bool:
    return any(
        message.get("role") in {"user", "assistant"}
        and isinstance(message.get("content"), str)
        and bool(message.get("content"))
        for message in messages
    )


def render_reasoning_options(selected: str) -> str:
    return "".join(
        f'<option value="{effort}"{" selected" if effort == selected else ""}>'
        f'{effort.capitalize()}</option>'
        for effort in REASONING_EFFORTS
    )


def render_login_page(*, username: str = USERNAME, error: str = "") -> bytes:
    username_html = html.escape(username)
    error_html = html.escape(error)
    error_section = f'<div class="login-error">{error_html}</div>' if error_html else ""
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in · Haibo's GLM-5.3-Flash</title>
<style>
* {{ box-sizing: border-box; }}
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ display: grid; min-height: 100vh; margin: 0; place-items: center; padding: 1.25rem; color: #ededed; background: #111; }}
.login-card {{ width: min(100%, 420px); padding: 2rem; border: 1px solid #303030; border-radius: 1.4rem; background: #1b1b1b; box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35); }}
.brand {{ margin-bottom: 1.8rem; text-align: center; }}
.brand h1 {{ margin: 0; font-size: 1.65rem; letter-spacing: -0.035em; }}
.brand p {{ margin: 0.55rem 0 0; color: #888; font-size: 0.92rem; }}
label {{ display: block; margin: 0 0 0.4rem; color: #aaa; font-size: 0.88rem; }}
input {{ width: 100%; margin-bottom: 1rem; padding: 0.82rem 0.9rem; border: 1px solid #383838; border-radius: 0.75rem; outline: 0; color: #eee; background: #121212; }}
input:focus {{ border-color: #666; box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.05); }}
button {{ width: 100%; margin-top: 0.25rem; padding: 0.82rem; border: 0; border-radius: 0.75rem; color: white; background: #2f6fdb; cursor: pointer; font: inherit; font-weight: 650; }}
button:hover {{ background: #3d7be3; }}
.login-error {{ margin-bottom: 1rem; padding: 0.75rem; border: 1px solid #713939; border-radius: 0.7rem; color: #ffb4b4; background: #2a1717; font-size: 0.9rem; }}
</style>
</head>
<body>
<main class="login-card">
<header class="brand">
<h1>Haibo's GLM-5.3-Flash</h1>
<p>Sign in to continue</p>
</header>
{error_section}
<form method="post" action="/login">
<label for="username">Username</label>
<input id="username" name="username" value="{username_html}" autocomplete="username" required autofocus>
<label for="password">Password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Sign in</button>
</form>
</main>
</body>
</html>
"""
    return page.encode("utf-8")


def render_usage(state: UsageState) -> str:
    context_usage = state.current_context_tokens / CONTEXT_WINDOW * 100
    return f"""
<section class="usage">
<div class="usage-card">
<h2>Turn Usage</h2>
<div>Input tokens: {state.turn.input_tokens:,}</div>
<div>Output tokens: {state.turn.output_tokens:,}</div>
<div>Total tokens: {state.turn.total_tokens:,}</div>
</div>
<div class="usage-card">
<h2>Conversation Usage</h2>
<div>Input tokens: {state.conversation.input_tokens:,}</div>
<div>Output tokens: {state.conversation.output_tokens:,}</div>
<div>Total tokens: {state.conversation.total_tokens:,}</div>
</div>
<div class="usage-card context-usage">
<h2>Current Context</h2>
<div>{state.current_context_tokens:,}/{CONTEXT_WINDOW:,} ({context_usage:.2f}%)</div>
</div>
</section>
"""


def render_page(
    *,
    conversation_id: str,
    messages: list[Message] | None = None,
    usage_state: UsageState | None = None,
    prompt: str = "",
    error: str = "",
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> bytes:
    conversation_id = validate_conversation_id(conversation_id)
    conversation_url = f"/chat/{conversation_id}"
    messages = messages or []
    if reasoning_effort not in REASONING_EFFORTS:
        reasoning_effort = DEFAULT_REASONING_EFFORT

    history_html = render_history(messages)
    usage_html = render_usage(usage_state or UsageState())
    reasoning_options = render_reasoning_options(reasoning_effort)
    reasoning_label = reasoning_effort.capitalize()
    page_class = "chat-page" if has_visible_messages(messages) else "landing-page"
    prompt_html = html.escape(prompt)
    error_html = html.escape(error)
    error_section = ""
    if error_html:
        error_section = f'<section class="error"><h2>Error</h2><pre>{error_html}</pre></section>'

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haibo's GLM-5.3-Flash</title>
<style>
* {{ box-sizing: border-box; }}
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ min-height: 100vh; margin: 0; color: #ededed; background: #111; }}
button, textarea, select {{ font: inherit; }}
button, select {{ color: inherit; }}
.shell {{ width: min(100%, 980px); min-height: 100vh; margin: 0 auto; padding: 3rem 1.25rem; }}
.landing-page .shell {{ display: flex; flex-direction: column; justify-content: center; padding-bottom: 8vh; }}
.brand {{ margin-bottom: 1.6rem; text-align: center; }}
.brand h1 {{ margin: 0; color: #f1f1f1; font-size: clamp(2.2rem, 6vw, 4.4rem); font-weight: 650; letter-spacing: -0.055em; }}
.chat-page .brand {{ margin-bottom: 2rem; text-align: left; }}
.chat-page .brand h1 {{ font-size: clamp(1.7rem, 4vw, 2.5rem); }}
.history {{ display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem; }}
.landing-page .history {{ display: none; }}
.message {{ max-width: 100%; }}
.message > pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; line-height: 1.55; }}
.user {{ width: fit-content; max-width: min(78%, 720px); margin-left: auto; padding: 0.72rem 1rem; border-radius: 1.25rem; color: #fff; background: #24579b; }}
.assistant {{ padding: 0.45rem 0.25rem 1rem; }}
.markdown-body {{ line-height: 1.65; }}
.markdown-body > :first-child {{ margin-top: 0; }}
.markdown-body > :last-child {{ margin-bottom: 0; }}
.markdown-body pre {{ overflow-x: auto; padding: 0.9rem; border: 1px solid #333; border-radius: 0.65rem; background: #121212; }}
.markdown-body code {{ font-family: "SFMono-Regular", Consolas, monospace; }}
.markdown-body :not(pre) > code {{ padding: 0.12rem 0.32rem; border-radius: 0.3rem; background: #303030; }}
.markdown-body blockquote {{ margin-left: 0; padding-left: 1rem; border-left: 3px solid #555; color: #b8b8b8; }}
.markdown-body table {{ width: 100%; border-collapse: collapse; }}
.markdown-body th, .markdown-body td {{ padding: 0.5rem; border: 1px solid #3a3a3a; text-align: left; }}
.markdown-body a {{ color: #a8c7fa; overflow-wrap: anywhere; }}
.composer {{ display: grid; gap: 0.55rem; padding: 0.7rem 0.7rem 0.6rem 1rem; border: 1px solid #383838; border-radius: 1.6rem; background: #202020; box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28); }}
.composer:focus-within {{ border-color: #555; }}
.composer textarea {{ display: block; flex: 1; width: 100%; min-height: 1.75rem; max-height: 10rem; padding: 0.3rem 0; resize: none; overflow-y: auto; border: 0; outline: 0; color: #f0f0f0; background: transparent; line-height: 1.45; }}
.composer textarea::placeholder {{ color: #777; }}
.composer-footer {{ display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }}
.effort-control {{ position: relative; display: inline-flex; color: #a7a7a7; font-size: 0.88rem; }}
.effort-display {{ display: flex; height: 2.35rem; align-items: center; justify-content: center; gap: 0.42rem; padding: 0 0.75rem; border: 1px solid #3b3b3b; border-radius: 999px; line-height: 1; background: #181818; }}
.effort-arrow {{ color: #888; transform: translateY(-0.08rem); }}
.effort-control select {{ position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }}
.sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
.send-button {{ display: grid; width: 2.35rem; height: 2.35rem; place-items: center; border: 0; border-radius: 50%; color: #fff; background: #2f6fdb; cursor: pointer; font-size: 1.2rem; line-height: 1; }}
.send-button:hover {{ background: #3d7be3; }}
.send-button:disabled {{ cursor: wait; opacity: 0.45; }}
.new-form {{ margin-top: 0.85rem; text-align: center; }}
.new-button {{ padding: 0.55rem 0.9rem; border: 1px solid #383838; border-radius: 999px; color: #aaa; background: transparent; cursor: pointer; }}
.new-button:hover {{ color: #eee; border-color: #555; }}
.logout-form {{ position: fixed; top: 1rem; right: 1rem; z-index: 2; }}
.logout-button {{ padding: 0.45rem 0.7rem; border: 1px solid #333; border-radius: 999px; color: #888; background: #171717; cursor: pointer; font-size: 0.82rem; }}
.logout-button:hover {{ color: #ddd; border-color: #555; }}
.usage {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; margin: 2rem 0 1rem; color: #aaa; font-size: 0.86rem; }}
.usage-card {{ padding: 0.85rem; border: 1px solid #303030; border-radius: 0.8rem; background: #181818; }}
.usage-card h2 {{ margin: 0 0 0.45rem; color: #d7d7d7; font-size: 0.9rem; }}
.context-usage {{ grid-column: 1 / -1; }}
.error {{ margin-bottom: 1rem; padding: 0.9rem; border: 1px solid #713939; border-radius: 0.8rem; color: #ffb4b4; background: #2a1717; }}
.error h2 {{ margin-top: 0; font-size: 1rem; }}
.error pre {{ margin-bottom: 0; white-space: pre-wrap; }}
.thinking {{ display: flex; align-items: center; justify-content: center; gap: 0.65rem; margin-top: 1rem; color: #aaa; }}
.thinking[hidden] {{ display: none; }}
.spinner {{
    width: 1.1rem;
    height: 1.1rem;
    border: 2px solid #444;
    border-top-color: #ddd;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ .spinner {{ animation-duration: 1.6s; }} }}
@media (max-width: 600px) {{
    .shell {{ padding: 1.5rem 0.85rem; }}
    .brand h1 {{ font-size: 2rem; letter-spacing: -0.04em; }}
    .composer {{ border-radius: 1.2rem; }}
    .effort-display {{ height: 2.35rem; }}
    .usage {{ grid-template-columns: 1fr; }}
    .context-usage {{ grid-column: auto; }}
}}
</style>
</head>
<body class="{page_class}">
<form class="logout-form" method="post" action="/logout">
<button class="logout-button" type="submit">Log out</button>
</form>
<main class="shell">
<header class="brand"><h1>Haibo's GLM-5.3-Flash</h1></header>
<div class="history">{history_html}</div>
{error_section}
<form id="run-form" class="composer" method="post" action="{conversation_url}/run">
<textarea id="prompt" name="prompt" rows="1" placeholder="Ask anything, or task an agent..." required>{prompt_html}</textarea>
<div class="composer-footer">
<div class="effort-control">
<label class="sr-only" for="reasoning-effort">Reasoning effort</label>
<div class="effort-display" aria-hidden="true">
<span id="effort-value">{reasoning_label}</span><span class="effort-arrow">⌄</span>
</div>
<select id="reasoning-effort" name="reasoning_effort">{reasoning_options}</select>
</div>
<button id="send-button" class="send-button" type="submit" aria-label="Send">&#8593;</button>
</div>
</form>
<form class="new-form" method="post" action="/new">
<button id="new-button" class="new-button" type="submit">New Conversation</button>
</form>
{usage_html}
<div id="thinking" class="thinking" role="status" aria-live="polite" hidden>
<span class="spinner" aria-hidden="true"></span>
<span>Model is thinking...</span>
</div>
</main>
<script>
const runForm = document.getElementById("run-form");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("send-button");
const newButton = document.getElementById("new-button");
const reasoningEffort = document.getElementById("reasoning-effort");
const effortValue = document.getElementById("effort-value");
const thinking = document.getElementById("thinking");

function resizePrompt() {{
    promptInput.style.height = "auto";
    promptInput.style.height = Math.min(promptInput.scrollHeight, 160) + "px";
}}

function syncEffortLabel() {{
    effortValue.textContent = reasoningEffort.options[reasoningEffort.selectedIndex].text;
}}

promptInput.addEventListener("input", resizePrompt);
reasoningEffort.addEventListener("change", syncEffortLabel);

runForm.addEventListener("submit", () => {{
    promptInput.readOnly = true;
    sendButton.disabled = true;
    newButton.disabled = true;
    thinking.hidden = false;
}});

window.addEventListener("pageshow", () => {{
    promptInput.readOnly = false;
    sendButton.disabled = false;
    newButton.disabled = false;
    thinking.hidden = true;
    resizePrompt();
    syncEffortLabel();
}});
</script>
</body>
</html>
"""
    return page.encode("utf-8")


def render_current_page(
    *,
    conversation_id: str,
    prompt: str = "",
    error: str = "",
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> bytes:
    return render_page(
        conversation_id=conversation_id,
        messages=load_messages(conversation_id),
        usage_state=load_usage_state(conversation_id),
        prompt=prompt,
        error=error,
        reasoning_effort=reasoning_effort,
    )


class AgentRequestHandler(BaseHTTPRequestHandler):
    access_token = ""
    session_token = ""

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/login":
            if self._is_authenticated():
                self._redirect_new_conversation(DEFAULT_REASONING_EFFORT)
            else:
                self._send_html(200, render_login_page())
            return
        if not self._is_authenticated():
            self._redirect("/login")
            return
        if url.path == "/":
            self._redirect_new_conversation(DEFAULT_REASONING_EFFORT)
            return
        conversation_id = self._conversation_id_from_path(url.path)
        if conversation_id is None:
            self.send_error(404)
            return
        query = parse_qs(url.query)
        reasoning_effort = query.get("reasoning_effort", [DEFAULT_REASONING_EFFORT])[0]
        if reasoning_effort not in REASONING_EFFORTS:
            reasoning_effort = DEFAULT_REASONING_EFFORT
        try:
            with conversation_lock(conversation_id):
                page = render_current_page(
                    conversation_id=conversation_id,
                    reasoning_effort=reasoning_effort,
                )
            self._send_html(200, page)
        except Exception as exc:
            self._send_html(
                500,
                render_page(
                    conversation_id=conversation_id,
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )

    def do_POST(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/login":
            self._login()
            return
        if not self._is_authenticated():
            self._redirect("/login")
            return
        if url.path == "/logout":
            self._logout()
            return
        if url.path == "/new":
            self._redirect_new_conversation(DEFAULT_REASONING_EFFORT)
            return
        conversation_id = self._conversation_id_from_path(url.path, action="run")
        if conversation_id is None:
            self.send_error(404)
            return

        try:
            form = self._read_form()
        except ValueError:
            self._send_html(
                400,
                render_current_page(
                    conversation_id=conversation_id,
                    error="Invalid request size.",
                ),
            )
            return
        prompt = form.get("prompt", [""])[0].strip()
        reasoning_effort = form.get("reasoning_effort", [DEFAULT_REASONING_EFFORT])[0]
        if reasoning_effort not in REASONING_EFFORTS:
            self._send_html(
                400,
                render_current_page(
                    conversation_id=conversation_id,
                    prompt=prompt,
                    error="Reasoning effort must be low, high, or max.",
                ),
            )
            return
        if not prompt:
            self._send_html(
                400,
                render_current_page(
                    conversation_id=conversation_id,
                    error="Prompt is required.",
                    reasoning_effort=reasoning_effort,
                ),
            )
            return
        if len(prompt) > MAX_PROMPT_CHARS:
            self._send_html(
                400,
                render_current_page(
                    conversation_id=conversation_id,
                    prompt=prompt,
                    error=f"Prompt exceeds {MAX_PROMPT_CHARS} characters.",
                    reasoning_effort=reasoning_effort,
                ),
            )
            return

        try:
            conversation_path, usage_path, trace_path = conversation_paths(conversation_id)
            with conversation_lock(conversation_id):
                agent = create_agent(
                    conversation_path=conversation_path,
                    usage_path=usage_path,
                    trace_path=trace_path,
                    reasoning_effort=reasoning_effort,
                )
                agent.run(prompt)
            self._redirect_conversation(conversation_id, reasoning_effort)
        except Exception as exc:
            traceback.print_exc()
            self._send_html(
                500,
                render_current_page(
                    conversation_id=conversation_id,
                    prompt=prompt,
                    error=f"{type(exc).__name__}: {exc}",
                    reasoning_effort=reasoning_effort,
                ),
            )

    def _login(self) -> None:
        try:
            form = self._read_form()
        except ValueError:
            self._send_html(400, render_login_page(error="Invalid request."))
            return

        username = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]
        username_matches = hmac.compare_digest(username, USERNAME)
        password_matches = hmac.compare_digest(password, self.access_token)
        if not (username_matches and password_matches):
            self._send_html(
                401,
                render_login_page(username=username, error="Incorrect username or password."),
            )
            return

        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = self.session_token
        cookie[SESSION_COOKIE_NAME]["path"] = "/"
        cookie[SESSION_COOKIE_NAME]["httponly"] = True
        cookie[SESSION_COOKIE_NAME]["samesite"] = "Strict"
        if self._is_https_request():
            cookie[SESSION_COOKIE_NAME]["secure"] = True

        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", cookie.output(header="").strip())
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _logout(self) -> None:
        self.__class__.session_token = secrets.token_urlsafe(32)
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = ""
        cookie[SESSION_COOKIE_NAME]["path"] = "/"
        cookie[SESSION_COOKIE_NAME]["httponly"] = True
        cookie[SESSION_COOKIE_NAME]["samesite"] = "Strict"
        cookie[SESSION_COOKIE_NAME]["max-age"] = 0
        if self._is_https_request():
            cookie[SESSION_COOKIE_NAME]["secure"] = True

        self.send_response(303)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", cookie.output(header="").strip())
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _is_authenticated(self) -> bool:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        session = cookie.get(SESSION_COOKIE_NAME)
        return session is not None and hmac.compare_digest(session.value, self.session_token)

    def _is_https_request(self) -> bool:
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "")
        return forwarded_proto.split(",", 1)[0].strip().lower() == "https"

    def _read_form(self) -> dict[str, list[str]]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request size")
        try:
            body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("request body must be UTF-8") from exc
        return parse_qs(body, keep_blank_values=True)

    def _send_html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _conversation_id_from_path(path: str, action: str | None = None) -> str | None:
        parts = path.strip("/").split("/")
        expected_parts = 3 if action else 2
        if len(parts) != expected_parts or parts[0] != "chat":
            return None
        if action and parts[2] != action:
            return None
        try:
            return validate_conversation_id(parts[1])
        except ValueError:
            return None

    def _redirect_new_conversation(self, reasoning_effort: str) -> None:
        self._redirect_conversation(str(uuid4()), reasoning_effort)

    def _redirect_conversation(self, conversation_id: str, reasoning_effort: str) -> None:
        conversation_id = validate_conversation_id(conversation_id)
        self._redirect(f"/chat/{conversation_id}?reasoning_effort={reasoning_effort}")

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main() -> None:
    access_token = os.environ.get("AGENT_ACCESS_TOKEN", "")
    if not access_token:
        raise SystemExit("AGENT_ACCESS_TOKEN must be set")

    AgentRequestHandler.access_token = access_token
    AgentRequestHandler.session_token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((HOST, PORT), AgentRequestHandler)
    print(f"Agent web server: http://{HOST}:{PORT}")
    print(f"Username: {USERNAME}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
