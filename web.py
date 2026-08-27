"""Minimal password-protected web entry point for the agent harness."""

from __future__ import annotations

import hmac
import html
import hashlib
import json
import os
import re
import secrets
import shutil
import traceback
from datetime import datetime
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
SESSION_COOKIE_NAME = "haibo_agent_session"
MAX_PROMPT_CHARS = 20_000
MAX_REQUEST_BYTES = 64 * 1024
PASSWORD_HASH_ITERATIONS = 600_000
DEFAULT_REASONING_EFFORT = "max"
REASONING_EFFORTS = ("low", "high", "max")
USERS_PATH = Path("./tmp/web_users.json")
USER_WORKSPACES_ROOT = Path("./tmp/users")
USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,32}")
USER_LOCKS: dict[str, Lock] = {}
USER_LOCKS_GUARD = Lock()
CONVERSATION_LOCKS: dict[tuple[str, str], Lock] = {}
CONVERSATION_LOCKS_GUARD = Lock()
SESSIONS: dict[str, str] = {}
SESSIONS_LOCK = Lock()
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


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    username = normalize_username(username)
    if USERNAME_PATTERN.fullmatch(username) is None:
        raise ValueError("Username must be 3-32 characters using lowercase letters, numbers, or underscores.")
    return username


def user_root(username: str) -> Path:
    username = validate_username(username)
    return USER_WORKSPACES_ROOT / username


def validate_conversation_id(conversation_id: str) -> str:
    try:
        created_at, uuid_part = conversation_id.split("_", 1)
        datetime.strptime(created_at, "%Y%m%d-%H%M%S")
        parsed = UUID(uuid_part)
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid conversation id") from exc
    if str(parsed) != uuid_part:
        raise ValueError("invalid conversation id")
    return conversation_id


def new_conversation_id() -> str:
    created_at = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return f"{created_at}_{uuid4()}"


def conversations_root(username: str) -> Path:
    return user_root(username) / "conversations"


def conversation_paths(username: str, conversation_id: str) -> tuple[Path, Path, Path, Path]:
    conversation_id = validate_conversation_id(conversation_id)
    directory = conversations_root(username) / conversation_id
    return (
        directory / "conversation.json",
        directory / "usage.json",
        directory / "trace.txt",
        directory / "metadata.json",
    )


def legacy_user_paths(username: str) -> tuple[Path, Path, Path]:
    directory = user_root(username)
    return (
        directory / "conversation.json",
        directory / "usage.json",
        directory / "trace.txt",
    )


def user_lock(username: str) -> Lock:
    username = validate_username(username)
    with USER_LOCKS_GUARD:
        return USER_LOCKS.setdefault(username, Lock())


def conversation_lock(username: str, conversation_id: str) -> Lock:
    key = (validate_username(username), validate_conversation_id(conversation_id))
    with CONVERSATION_LOCKS_GUARD:
        return CONVERSATION_LOCKS.setdefault(key, Lock())


def load_messages(username: str, conversation_id: str) -> list[Message]:
    conversation_path, _, _, _ = conversation_paths(username, conversation_id)
    store = JsonConversationStore(conversation_path)
    if not store.exists():
        return []
    return store.load()


def load_usage_state(username: str, conversation_id: str) -> UsageState:
    _, usage_path, _, _ = conversation_paths(username, conversation_id)
    store = JsonUsageStore(usage_path)
    if not store.exists():
        return UsageState()
    return store.load()


def conversation_title(messages: list[Message]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            compact = " ".join(content.split())
            return compact[:48] + ("…" if len(compact) > 48 else "")
    return "New chat"


def write_conversation_metadata(
    username: str,
    conversation_id: str,
    *,
    title: str,
    created_at: str,
    updated_at: str,
) -> None:
    _, _, _, metadata_path = conversation_paths(username, conversation_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "id": conversation_id,
        "title": title,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    temporary_path = metadata_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(metadata_path)


def read_conversation_metadata(username: str, conversation_id: str) -> dict[str, str]:
    _, _, _, metadata_path = conversation_paths(username, conversation_id)
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = ("id", "title", "created_at", "updated_at")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) for key in required):
        raise ValueError(f"Invalid conversation metadata: {metadata_path}")
    if data["id"] != conversation_id:
        raise ValueError(f"Conversation metadata ID mismatch: {metadata_path}")
    return {key: data[key] for key in required}


def create_conversation(username: str) -> str:
    username = validate_username(username)
    with user_lock(username):
        conversation_id = new_conversation_id()
        now = datetime.now().astimezone().isoformat(timespec="microseconds")
        write_conversation_metadata(
            username,
            conversation_id,
            title="New chat",
            created_at=now,
            updated_at=now,
        )
        return conversation_id


def list_conversations(username: str) -> list[dict[str, str]]:
    root = conversations_root(username)
    if not root.is_dir():
        return []
    conversations = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        try:
            conversation_id = validate_conversation_id(directory.name)
            conversations.append(read_conversation_metadata(username, conversation_id))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    conversations.sort(key=lambda item: item["updated_at"], reverse=True)
    return conversations


def migrate_legacy_conversation(username: str) -> str | None:
    legacy_paths = legacy_user_paths(username)
    if not any(path.exists() for path in legacy_paths):
        return None
    conversation_id = new_conversation_id()
    new_paths = conversation_paths(username, conversation_id)
    new_paths[0].parent.mkdir(parents=True, exist_ok=False)
    for old_path, new_path in zip(legacy_paths, new_paths[:3]):
        if old_path.exists():
            old_path.replace(new_path)
    messages = JsonConversationStore(new_paths[0]).load() if new_paths[0].exists() else []
    now = datetime.now().astimezone().isoformat(timespec="microseconds")
    write_conversation_metadata(
        username,
        conversation_id,
        title=conversation_title(messages),
        created_at=now,
        updated_at=now,
    )
    return conversation_id


def ensure_user_conversation(username: str) -> str:
    username = validate_username(username)
    with user_lock(username):
        migrated_id = migrate_legacy_conversation(username)
        conversations = list_conversations(username)
        if conversations:
            return migrated_id or conversations[0]["id"]
        conversation_id = new_conversation_id()
        now = datetime.now().astimezone().isoformat(timespec="microseconds")
        write_conversation_metadata(
            username,
            conversation_id,
            title="New chat",
            created_at=now,
            updated_at=now,
        )
        return conversation_id


def update_conversation_metadata(username: str, conversation_id: str, prompt: str) -> None:
    metadata = read_conversation_metadata(username, conversation_id)
    if metadata["title"] == "New chat":
        metadata["title"] = conversation_title([{"role": "user", "content": prompt}])
    metadata["updated_at"] = datetime.now().astimezone().isoformat(timespec="microseconds")
    write_conversation_metadata(username, conversation_id, **{
        "title": metadata["title"],
        "created_at": metadata["created_at"],
        "updated_at": metadata["updated_at"],
    })


def hash_password(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    ).hex()


class JsonUserStore:
    """Small persistent user database with salted PBKDF2 password hashes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock = Lock()

    def ensure_user(self, username: str, password: str) -> None:
        username = validate_username(username)
        with self.lock:
            data = self._load_unlocked()
            if username in data["users"]:
                return
            data["users"][username] = self._password_record(password)
            self._save_unlocked(data)

    def create_user(self, username: str, password: str) -> bool:
        username = validate_username(username)
        with self.lock:
            data = self._load_unlocked()
            if username in data["users"]:
                return False
            data["users"][username] = self._password_record(password)
            self._save_unlocked(data)
            return True

    def authenticate(self, username: str, password: str) -> bool:
        try:
            username = validate_username(username)
        except ValueError:
            return False
        with self.lock:
            record = self._load_unlocked()["users"].get(username)
        if not isinstance(record, dict):
            return False
        try:
            salt = bytes.fromhex(record["salt"])
            iterations = int(record["iterations"])
            expected = str(record["password_hash"])
        except (KeyError, TypeError, ValueError):
            return False
        actual = hash_password(password, salt, iterations)
        return hmac.compare_digest(actual, expected)

    def _password_record(self, password: str) -> dict[str, str | int]:
        salt = secrets.token_bytes(16)
        return {
            "salt": salt.hex(),
            "password_hash": hash_password(password, salt, PASSWORD_HASH_ITERATIONS),
            "iterations": PASSWORD_HASH_ITERATIONS,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    def _load_unlocked(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": 1, "users": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("users"), dict)
        ):
            raise ValueError(f"Invalid user database: {self.path}")
        return data

    def _save_unlocked(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.chmod(0o600)
        os.replace(temporary_path, self.path)


USER_STORE = JsonUserStore(USERS_PATH)


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
        if role == "user" and isinstance(content, str) and content:
            rendered.append(
                f'<section class="message user" aria-label="You"><pre>{html.escape(content)}</pre></section>'
            )
            continue
        if role == "assistant":
            trace_parts = []
            reasoning = message.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                trace_parts.append(
                    '<details class="trace-entry">'
                    '<summary>Reasoning</summary>'
                    f'<pre>{html.escape(reasoning)}</pre>'
                    '</details>'
                )
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function")
                    if not isinstance(function, dict):
                        continue
                    name = html.escape(str(function.get("name", "tool")))
                    arguments = html.escape(
                        json.dumps(function.get("arguments", {}), ensure_ascii=False, indent=2)
                    )
                    trace_parts.append(
                        '<details class="trace-entry">'
                        f'<summary>Tool call · {name}</summary>'
                        f'<pre>{arguments}</pre>'
                        '</details>'
                    )
            answer = (
                f'<div class="markdown-body">{render_markdown(content)}</div>'
                if isinstance(content, str) and content
                else ""
            )
            if trace_parts or answer:
                trace = f'<div class="trace-stack">{"".join(trace_parts)}</div>' if trace_parts else ""
                rendered.append(
                    f'<section class="message assistant" aria-label="Assistant">{trace}{answer}</section>'
                )
            continue
        if role == "tool" and isinstance(content, str):
            name = html.escape(str(message.get("name", "tool")))
            rendered.append(
                '<section class="message tool-message" aria-label="Tool result">'
                '<details class="trace-entry">'
                f'<summary>Tool result · {name}</summary>'
                f'<pre>{html.escape(content)}</pre>'
                '</details>'
                '</section>'
            )
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


def render_auth_page(
    *,
    mode: str,
    username: str = "",
    error: str = "",
) -> bytes:
    if mode not in {"login", "register"}:
        raise ValueError("invalid authentication page mode")
    is_register = mode == "register"
    username_html = html.escape(username)
    error_html = html.escape(error)
    error_section = f'<div class="auth-error">{error_html}</div>' if error_html else ""
    title = "Create account" if is_register else "Sign in"
    subtitle = "Register to start your conversation" if is_register else "Sign in to continue"
    action = "/register" if is_register else "/login"
    password_autocomplete = "new-password" if is_register else "current-password"
    confirm_password = ""
    if is_register:
        confirm_password = f"""
<label for="confirm-password">Confirm password</label>
<input id="confirm-password" name="confirm_password" type="password" autocomplete="new-password" required>
"""
    alternate = (
        '<p class="auth-switch">Already have an account? <a href="/login">Sign in</a></p>'
        if is_register
        else '<p class="auth-switch">New here? <a href="/register">Create an account</a></p>'
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Haibo's GLM-5.3-Flash</title>
<style>
* {{ box-sizing: border-box; }}
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ display: grid; min-height: 100vh; margin: 0; place-items: center; padding: 1.25rem; color: #ededed; background: #111; }}
.auth-card {{ width: min(100%, 420px); padding: 2rem; border: 1px solid #303030; border-radius: 1.4rem; background: #1b1b1b; box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35); }}
.brand {{ margin-bottom: 1.8rem; text-align: center; }}
.brand h1 {{ margin: 0; font-size: 1.65rem; letter-spacing: -0.035em; }}
.brand p {{ margin: 0.55rem 0 0; color: #888; font-size: 0.92rem; }}
label {{ display: block; margin: 0 0 0.4rem; color: #aaa; font-size: 0.88rem; }}
input {{ width: 100%; margin-bottom: 1rem; padding: 0.82rem 0.9rem; border: 1px solid #383838; border-radius: 0.75rem; outline: 0; color: #eee; background: #121212; }}
input:focus {{ border-color: #666; box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.05); }}
button {{ width: 100%; margin-top: 0.25rem; padding: 0.82rem; border: 0; border-radius: 0.75rem; color: white; background: #2f6fdb; cursor: pointer; font: inherit; font-weight: 650; }}
button:hover {{ background: #3d7be3; }}
.auth-error {{ margin-bottom: 1rem; padding: 0.75rem; border: 1px solid #713939; border-radius: 0.7rem; color: #ffb4b4; background: #2a1717; font-size: 0.9rem; }}
.auth-switch {{ margin: 1.2rem 0 0; color: #888; text-align: center; font-size: 0.88rem; }}
.auth-switch a {{ color: #b9cdf3; text-decoration: none; }}
.auth-switch a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<main class="auth-card">
<header class="brand">
<h1>Haibo's GLM-5.3-Flash</h1>
<p>{subtitle}</p>
</header>
{error_section}
<form method="post" action="{action}">
<label for="username">Username</label>
<input id="username" name="username" value="{username_html}" minlength="3" maxlength="32" pattern="[a-z0-9_]+" autocomplete="username" required autofocus>
<label for="password">Password</label>
<input id="password" name="password" type="password" autocomplete="{password_autocomplete}" required>
{confirm_password}
<button type="submit">{title}</button>
</form>
{alternate}
</main>
</body>
</html>
"""
    return page.encode("utf-8")


def render_login_page(*, username: str = "", error: str = "") -> bytes:
    return render_auth_page(mode="login", username=username, error=error)


def render_register_page(*, username: str = "", error: str = "") -> bytes:
    return render_auth_page(mode="register", username=username, error=error)


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


def render_sidebar(
    username: str,
    conversations: list[dict[str, str]],
    current_conversation_id: str,
) -> str:
    items = []
    for conversation in conversations:
        conversation_id = validate_conversation_id(conversation["id"])
        title = html.escape(conversation["title"])
        active = " active" if conversation_id == current_conversation_id else ""
        items.append(
            f"""
<div class="conversation-item{active}">
<a class="conversation-link" href="/chat/{conversation_id}" title="{title}">{title}</a>
<form class="delete-form" method="post" action="/chat/{conversation_id}/delete">
<button class="delete-button" type="submit" aria-label="Delete {title}" title="Delete conversation">&times;</button>
</form>
</div>
"""
        )
    history_items = "".join(items) or '<p class="no-conversations">No conversations yet</p>'
    return f"""
<button id="sidebar-toggle" class="sidebar-toggle" type="button" aria-label="Open conversation history" aria-controls="sidebar" aria-expanded="false">&#9776;</button>
<div id="sidebar-backdrop" class="sidebar-backdrop" hidden></div>
<aside id="sidebar" class="sidebar">
<div class="sidebar-header">
<div class="sidebar-brand">Haibo's GLM</div>
<button id="sidebar-close" class="sidebar-close" type="button" aria-label="Close conversation history">&times;</button>
</div>
<form method="post" action="/new">
<button id="new-button" class="new-chat-button" type="submit"><span aria-hidden="true">&#9998;</span> New chat</button>
</form>
<div class="history-label">Recent</div>
<nav class="conversation-list" aria-label="Conversation history">{history_items}</nav>
<div class="sidebar-account">
<div class="account-name" title="Signed in user">{html.escape(username)}</div>
<form method="post" action="/logout">
<button class="logout-button" type="submit">Log out</button>
</form>
</div>
</aside>
"""


def render_page(
    *,
    username: str,
    conversation_id: str,
    conversations: list[dict[str, str]],
    messages: list[Message] | None = None,
    usage_state: UsageState | None = None,
    prompt: str = "",
    error: str = "",
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> bytes:
    username = validate_username(username)
    conversation_id = validate_conversation_id(conversation_id)
    messages = messages or []
    if reasoning_effort not in REASONING_EFFORTS:
        reasoning_effort = DEFAULT_REASONING_EFFORT

    history_html = render_history(messages)
    sidebar_html = render_sidebar(username, conversations, conversation_id)
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
.sidebar {{ position: fixed; z-index: 20; inset: 0 auto 0 0; display: flex; width: 260px; flex-direction: column; padding: 0.9rem 0.7rem; border-right: 1px solid #272727; background: #0c0c0c; }}
.sidebar-header {{ display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0.45rem 0.9rem; }}
.sidebar-brand {{ color: #eee; font-weight: 650; letter-spacing: -0.02em; }}
.sidebar-close, .sidebar-toggle {{ display: none; border: 0; color: #aaa; background: transparent; cursor: pointer; }}
.new-chat-button {{ display: flex; width: 100%; align-items: center; gap: 0.65rem; padding: 0.7rem 0.75rem; border: 1px solid #303030; border-radius: 0.75rem; color: #eee; background: #1b1b1b; cursor: pointer; text-align: left; }}
.new-chat-button:hover {{ background: #252525; }}
.history-label {{ padding: 1.35rem 0.65rem 0.45rem; color: #696969; font-size: 0.75rem; font-weight: 650; text-transform: uppercase; letter-spacing: 0.06em; }}
.conversation-list {{ min-height: 0; flex: 1; overflow-y: auto; }}
.conversation-item {{ display: flex; min-width: 0; align-items: center; margin: 0.1rem 0; border-radius: 0.65rem; }}
.conversation-item:hover, .conversation-item.active {{ background: #202020; }}
.conversation-link {{ min-width: 0; flex: 1; padding: 0.62rem 0.7rem; overflow: hidden; color: #bcbcbc; text-decoration: none; text-overflow: ellipsis; white-space: nowrap; font-size: 0.88rem; }}
.conversation-item.active .conversation-link {{ color: #f0f0f0; }}
.conversation-item form {{ flex: 0 0 auto; }}
.delete-button {{ width: 1.8rem; height: 1.8rem; margin-right: 0.25rem; border: 0; border-radius: 50%; color: transparent; background: transparent; cursor: pointer; line-height: 1; }}
.conversation-item:hover .delete-button, .conversation-item:focus-within .delete-button {{ color: #888; }}
.delete-button:hover {{ color: #ddd !important; background: #343434; }}
.no-conversations {{ padding: 0.6rem; color: #666; font-size: 0.82rem; }}
.sidebar-account {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 0.4rem 0.15rem; border-top: 1px solid #252525; }}
.account-name {{ min-width: 0; flex: 1; overflow: hidden; color: #999; text-overflow: ellipsis; white-space: nowrap; font-size: 0.82rem; }}
.logout-button {{ padding: 0.4rem 0.58rem; border: 1px solid #333; border-radius: 999px; color: #888; background: #171717; cursor: pointer; font-size: 0.76rem; }}
.logout-button:hover {{ color: #ddd; border-color: #555; }}
.main-content {{ min-height: 100vh; margin-left: 260px; }}
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
.tool-message {{ padding: 0 0.25rem 0.7rem; }}
.trace-stack {{ display: grid; gap: 0.42rem; margin: 0 0 0.8rem; }}
.trace-entry {{ border: 1px solid #303030; border-radius: 0.65rem; color: #929292; background-color: #171717; background-image: repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.018) 0, rgba(255, 255, 255, 0.018) 1px, transparent 1px, transparent 7px); font-size: 0.8rem; }}
.trace-entry summary {{ padding: 0.48rem 0.65rem; cursor: pointer; color: #9d9d9d; user-select: none; }}
.trace-entry[open] summary {{ border-bottom: 1px solid #2b2b2b; }}
.trace-entry pre {{ max-height: 14rem; margin: 0; padding: 0.65rem; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: #858585; font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.76rem; line-height: 1.5; }}
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
.live-answer-text {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: 1rem; line-height: 1.65; color: #ededed; }}
.thinking-line {{ display: flex; align-items: center; gap: 0.55rem; padding: 0.4rem 0.25rem 0.6rem; color: #9a9a9a; font-size: 0.9rem; }}
.thinking-label {{ color: #9a9a9a; }}
.thinking-dots {{ display: inline-flex; gap: 0.28rem; }}
.thinking-dots span {{ width: 0.42rem; height: 0.42rem; border-radius: 50%; background: #7aa2e3; animation: thinking-bounce 1.2s ease-in-out infinite; }}
.thinking-dots span:nth-child(2) {{ animation-delay: 0.18s; }}
.thinking-dots span:nth-child(3) {{ animation-delay: 0.36s; }}
@keyframes thinking-bounce {{ 0%, 80%, 100% {{ transform: scale(0.5); opacity: 0.35; }} 40% {{ transform: scale(1); opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{ .thinking-dots span {{ animation-duration: 2.4s; }} }}
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
.usage {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; margin: 2rem 0 1rem; color: #aaa; font-size: 0.86rem; }}
.usage-card {{ padding: 0.85rem; border: 1px solid #303030; border-radius: 0.8rem; background: #181818; }}
.usage-card h2 {{ margin: 0 0 0.45rem; color: #d7d7d7; font-size: 0.9rem; }}
.context-usage {{ grid-column: 1 / -1; }}
.site-footer {{ margin-top: 1.5rem; color: #686868; text-align: center; font-size: 0.75rem; line-height: 1.6; }}
.site-footer a {{ color: #858585; text-decoration: none; }}
.site-footer a:hover {{ color: #b5b5b5; text-decoration: underline; }}
.error {{ margin-bottom: 1rem; padding: 0.9rem; border: 1px solid #713939; border-radius: 0.8rem; color: #ffb4b4; background: #2a1717; }}
.error h2 {{ margin-top: 0; font-size: 1rem; }}
.error pre {{ margin-bottom: 0; white-space: pre-wrap; }}
.live-tool-status {{ padding: 0.45rem 0.65rem; color: #777; border-top: 1px solid #292929; }}
.activity-error {{ margin: 0.6rem 0; padding: 0.65rem; border: 1px solid #713939; border-radius: 0.6rem; color: #ffb4b4; background: #2a1717; white-space: pre-wrap; }}
@media (max-width: 760px) {{
    .sidebar {{ width: min(86vw, 300px); transform: translateX(-100%); transition: transform 0.2s ease; box-shadow: 18px 0 60px rgba(0, 0, 0, 0.45); }}
    .sidebar.open {{ transform: translateX(0); }}
    .sidebar-toggle {{ position: fixed; z-index: 15; top: 0.8rem; left: 0.75rem; display: grid; width: 2.25rem; height: 2.25rem; place-items: center; border: 1px solid #333; border-radius: 0.65rem; background: #181818; font-size: 1.1rem; }}
    .sidebar-close {{ display: block; width: 2rem; height: 2rem; font-size: 1.35rem; }}
    .sidebar-backdrop {{ position: fixed; z-index: 19; inset: 0; background: rgba(0, 0, 0, 0.6); }}
    .sidebar-backdrop[hidden] {{ display: none; }}
    .main-content {{ margin-left: 0; }}
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
{sidebar_html}
<div class="main-content">
<main class="shell">
<header class="brand"><h1>Haibo's GLM-5.3-Flash</h1></header>
<div class="history">{history_html}</div>
{error_section}
<form id="run-form" class="composer" method="post" action="/chat/{conversation_id}/run">
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
{usage_html}
<footer class="site-footer">
Powered by the custom-built <a href="https://github.com/WHB139426/pi_qwen/" target="_blank" rel="noopener noreferrer">pi_qwen</a> agent framework and Z.ai's <a href="https://docs.z.ai/guides/vlm/glm-5.3-flash" target="_blank" rel="noopener noreferrer">GLM-5.3-Flash</a>, locally deployed on 4&times; NVIDIA H200 GPUs.
</footer>
</main>
</div>
<script>
const runForm = document.getElementById("run-form");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("send-button");
const newButton = document.getElementById("new-button");
const reasoningEffort = document.getElementById("reasoning-effort");
const effortValue = document.getElementById("effort-value");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarClose = document.getElementById("sidebar-close");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const deleteForms = document.querySelectorAll(".delete-form");
const history = document.querySelector(".history");
const liveSteps = new Map();
const liveTools = new Map();
let thinkingLine = null;

function resizePrompt() {{
    promptInput.style.height = "auto";
    promptInput.style.height = Math.min(promptInput.scrollHeight, 160) + "px";
}}

function syncEffortLabel() {{
    effortValue.textContent = reasoningEffort.options[reasoningEffort.selectedIndex].text;
}}

promptInput.addEventListener("input", resizePrompt);
reasoningEffort.addEventListener("change", syncEffortLabel);

function setSidebar(open) {{
    sidebar.classList.toggle("open", open);
    sidebarBackdrop.hidden = !open;
    sidebarToggle.setAttribute("aria-expanded", String(open));
}}

sidebarToggle.addEventListener("click", () => setSidebar(true));
sidebarClose.addEventListener("click", () => setSidebar(false));
sidebarBackdrop.addEventListener("click", () => setSidebar(false));
deleteForms.forEach((form) => {{
    form.addEventListener("submit", (event) => {{
        if (!window.confirm("Delete this conversation permanently?")) {{
            event.preventDefault();
        }}
    }});
}});

function setRunning(running) {{
    promptInput.readOnly = running;
    sendButton.disabled = running;
    newButton.disabled = running;
    deleteForms.forEach((form) => {{ form.querySelector("button").disabled = running; }});
}}

function showThinking(label) {{
    if (!thinkingLine) {{
        thinkingLine = document.createElement("div");
        thinkingLine.className = "thinking-line";
        thinkingLine.innerHTML = '<span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span><span class="thinking-label"></span>';
    }}
    thinkingLine.querySelector(".thinking-label").textContent = label || "Thinking";
    history.append(thinkingLine);
    maybeScroll();
}}

function hideThinking() {{
    if (thinkingLine) {{ thinkingLine.remove(); thinkingLine = null; }}
}}

function ensureLiveTurn(stepNumber) {{
    if (liveSteps.has(stepNumber)) {{ return liveSteps.get(stepNumber); }}
    clearEmptyPlaceholder();
    const section = document.createElement("section");
    section.className = "message assistant";
    section.setAttribute("aria-label", "Assistant");

    const trace = document.createElement("div");
    trace.className = "trace-stack";

    const reasoning = document.createElement("details");
    reasoning.className = "trace-entry";
    reasoning.hidden = true;
    const summary = document.createElement("summary");
    summary.textContent = `Reasoning · Turn ${{stepNumber}}`;
    const reasoningPre = document.createElement("pre");
    reasoning.append(summary, reasoningPre);
    trace.append(reasoning);

    section.append(trace);
    history.append(section);

    const state = {{ raw: "", section, trace, reasoning, reasoningPre, contentEl: null }};
    liveSteps.set(stepNumber, state);
    return state;
}}

function updateReasoning(state, text) {{
    if (!text) {{ return; }}
    state.reasoning.hidden = false;
    state.reasoningPre.textContent = text;
}}

function ensureContentEl(state) {{
    if (state.contentEl) {{ return state.contentEl; }}
    const pre = document.createElement("pre");
    pre.className = "live-answer-text";
    state.section.append(pre);
    state.contentEl = pre;
    return pre;
}}

function setContent(state, text) {{
    if (!text) {{ return; }}
    ensureContentEl(state).textContent = text;
}}

function streamedReasoning(raw) {{
    const start = raw.indexOf("<think>");
    const reasoningStart = start >= 0 ? start + "<think>".length : 0;
    const end = raw.indexOf("</think>", reasoningStart);
    return raw.slice(reasoningStart, end >= 0 ? end : raw.length).trimStart();
}}

function streamedContent(raw) {{
    const marker = raw.indexOf("</think>");
    if (marker < 0) {{ return ""; }}
    let content = raw.slice(marker + "</think>".length);
    content = content.replace(/<tool_call\\b[\\s\\S]*?<\\/tool_call>/g, "");
    content = content.replace(/<tool_call\\b[\\s\\S]*$/, "");
    return content.trim();
}}

function maybeScroll() {{
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
    if (nearBottom) {{ window.scrollTo(0, document.body.scrollHeight); }}
}}

function clearEmptyPlaceholder() {{
    const empty = history.querySelector(".empty");
    if (empty) {{ empty.remove(); }}
}}

function appendUserMessage(text) {{
    clearEmptyPlaceholder();
    const section = document.createElement("section");
    section.className = "message user";
    section.setAttribute("aria-label", "You");
    const pre = document.createElement("pre");
    pre.textContent = text;
    section.append(pre);
    history.append(section);
}}

function addToolCall(event) {{
    const state = ensureLiveTurn(event.step);
    const details = document.createElement("details");
    details.className = "trace-entry";
    const summary = document.createElement("summary");
    summary.textContent = `Tool call · ${{event.name || "tool"}}`;
    const argumentsBlock = document.createElement("pre");
    argumentsBlock.textContent = JSON.stringify(event.arguments || {{}}, null, 2);
    const status = document.createElement("div");
    status.className = "live-tool-status";
    status.textContent = "Running…";
    details.append(summary, argumentsBlock, status);
    state.trace.append(details);
    liveTools.set(event.tool_call_id, {{ details, status }});
}}

function addToolResult(event) {{
    let tool = liveTools.get(event.tool_call_id);
    if (!tool) {{
        addToolCall(event);
        tool = liveTools.get(event.tool_call_id);
    }}
    tool.status.textContent = "Completed";
    const result = document.createElement("pre");
    result.textContent = String(event.content || "");
    tool.details.append(result);
}}

function showStreamError(message) {{
    hideThinking();
    const error = document.createElement("div");
    error.className = "activity-error";
    error.textContent = message;
    history.append(error);
    setRunning(false);
    maybeScroll();
}}

function handleAgentEvent(event) {{
    if (event.type === "stream_start") {{
        showThinking("Thinking");
        return;
    }}
    if (event.type === "generation_start") {{
        ensureLiveTurn(event.step);
        showThinking("Thinking");
        return;
    }}
    if (event.type === "model_delta") {{
        const state = ensureLiveTurn(event.step);
        state.raw += event.delta || "";
        updateReasoning(state, streamedReasoning(state.raw));
        const content = streamedContent(state.raw);
        if (content) {{
            setContent(state, content);
            showThinking("Writing");
        }} else {{
            showThinking("Thinking");
        }}
        maybeScroll();
        return;
    }}
    if (event.type === "assistant_message") {{
        const state = ensureLiveTurn(event.step);
        updateReasoning(state, event.reasoning_content || "");
        setContent(state, event.content || "");
        return;
    }}
    if (event.type === "tool_call") {{
        addToolCall(event);
        showThinking(`Using ${{event.name || "tool"}}`);
        maybeScroll();
        return;
    }}
    if (event.type === "tool_result") {{
        addToolResult(event);
        showThinking("Thinking");
        maybeScroll();
        return;
    }}
    if (event.type === "final_answer") {{
        const state = ensureLiveTurn(event.step);
        setContent(state, event.content || "");
        showThinking("Finalizing");
        return;
    }}
    if (event.type === "error") {{
        showStreamError(event.message || "Unknown agent error");
        return;
    }}
    if (event.type === "done") {{
        window.location.assign(event.redirect);
    }}
}}

async function runAgentStream(body) {{
    let response;
    try {{
        response = await fetch(runForm.action, {{
            method: "POST",
            body: body,
            headers: {{ "Accept": "text/event-stream" }},
        }});
    }} catch (err) {{
        const streamError = new Error("Live streaming request could not be established (" + err.message + ")");
        streamError.name = "StreamUnavailable";
        throw streamError;
    }}
    if (!response.ok || !response.body) {{
        throw new Error(`Request failed with status ${{response.status}}`);
    }}

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {{
        const {{ value, done }} = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), {{ stream: !done }});
        const frames = buffer.split("\\n\\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {{
            const data = frame.split("\\n")
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trimStart())
                .join("\\n");
            if (data) {{ handleAgentEvent(JSON.parse(data)); }}
        }}
        if (done) {{ break; }}
    }}
}}

runForm.addEventListener("submit", (event) => {{
    event.preventDefault();
    const promptText = promptInput.value;
    if (!promptText.trim()) {{ return; }}
    const body = new URLSearchParams(new FormData(runForm));
    appendUserMessage(promptText);
    document.body.classList.remove("landing-page");
    document.body.classList.add("chat-page");
    promptInput.value = "";
    resizePrompt();
    liveSteps.clear();
    liveTools.clear();
    setRunning(true);
    showThinking("Thinking");
    maybeScroll();
    runAgentStream(body)
        .then(() => {{ hideThinking(); }})
        .catch((error) => {{
            if (error && error.name === "StreamUnavailable") {{
                // A proxy, tunnel, or in-app browser is blocking the live stream.
                // Fall back to a plain form POST: the page reloads with the full
                // answer, just without the live typing animation.
                showThinking("");
                promptInput.value = promptText;
                runForm.submit();
                return;
            }}
            promptInput.value = promptText;
            resizePrompt();
            showStreamError(error.message);
        }});
}});

window.addEventListener("pageshow", () => {{
    setRunning(false);
    hideThinking();
    liveSteps.clear();
    liveTools.clear();
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
    username: str,
    conversation_id: str,
    prompt: str = "",
    error: str = "",
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> bytes:
    return render_page(
        username=username,
        conversation_id=conversation_id,
        conversations=list_conversations(username),
        messages=load_messages(username, conversation_id),
        usage_state=load_usage_state(username, conversation_id),
        prompt=prompt,
        error=error,
        reasoning_effort=reasoning_effort,
    )


class AgentRequestHandler(BaseHTTPRequestHandler):
    disable_nagle_algorithm = True

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/login":
            if self._authenticated_user() is not None:
                self._redirect_home(DEFAULT_REASONING_EFFORT)
            else:
                self._send_html(200, render_login_page())
            return
        if url.path == "/register":
            if self._authenticated_user() is not None:
                self._redirect_home(DEFAULT_REASONING_EFFORT)
            else:
                self._send_html(200, render_register_page())
            return
        username = self._authenticated_user()
        if username is None:
            self._redirect("/login")
            return
        if url.path == "/":
            self._redirect_conversation(
                ensure_user_conversation(username),
                DEFAULT_REASONING_EFFORT,
            )
            return
        conversation_id = self._conversation_id_from_path(url.path)
        if conversation_id is None:
            self.send_error(404)
            return
        _, _, _, metadata_path = conversation_paths(username, conversation_id)
        if not metadata_path.is_file():
            self.send_error(404)
            return
        query = parse_qs(url.query)
        reasoning_effort = query.get("reasoning_effort", [DEFAULT_REASONING_EFFORT])[0]
        if reasoning_effort not in REASONING_EFFORTS:
            reasoning_effort = DEFAULT_REASONING_EFFORT
        try:
            with conversation_lock(username, conversation_id):
                page = render_current_page(
                    username=username,
                    conversation_id=conversation_id,
                    reasoning_effort=reasoning_effort,
                )
            self._send_html(200, page)
        except Exception as exc:
            self._send_html(
                500,
                render_page(
                    username=username,
                    conversation_id=conversation_id,
                    conversations=list_conversations(username),
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )

    def do_POST(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/login":
            self._login()
            return
        if url.path == "/register":
            self._register()
            return
        username = self._authenticated_user()
        if username is None:
            self._redirect("/login")
            return
        if url.path == "/logout":
            self._logout()
            return
        if url.path == "/new":
            self._new_conversation(username)
            return
        delete_id = self._conversation_id_from_path(url.path, action="delete")
        if delete_id is not None:
            self._delete_conversation(username, delete_id)
            return
        conversation_id = self._conversation_id_from_path(url.path, action="run")
        if conversation_id is None:
            self.send_error(404)
            return
        _, _, _, metadata_path = conversation_paths(username, conversation_id)
        if not metadata_path.is_file():
            self.send_error(404)
            return

        try:
            form = self._read_form()
        except ValueError:
            self._send_html(
                400,
                render_current_page(
                    username=username,
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
                    username=username,
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
                    username=username,
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
                    username=username,
                    conversation_id=conversation_id,
                    prompt=prompt,
                    error=f"Prompt exceeds {MAX_PROMPT_CHARS} characters.",
                    reasoning_effort=reasoning_effort,
                ),
            )
            return

        if "text/event-stream" in self.headers.get("Accept", ""):
            self._stream_agent_run(
                username,
                conversation_id,
                prompt,
                reasoning_effort,
            )
            return

        try:
            self._run_agent(
                username,
                conversation_id,
                prompt,
                reasoning_effort,
            )
            self._redirect_conversation(conversation_id, reasoning_effort)
        except Exception as exc:
            traceback.print_exc()
            self._send_html(
                500,
                render_current_page(
                    username=username,
                    conversation_id=conversation_id,
                    prompt=prompt,
                    error=f"{type(exc).__name__}: {exc}",
                    reasoning_effort=reasoning_effort,
                ),
            )

    def _run_agent(
        self,
        username: str,
        conversation_id: str,
        prompt: str,
        reasoning_effort: str,
        *,
        event_callback=None,
    ) -> None:
        conversation_path, usage_path, trace_path, _ = conversation_paths(
            username,
            conversation_id,
        )
        with conversation_lock(username, conversation_id):
            agent = create_agent(
                conversation_path=conversation_path,
                usage_path=usage_path,
                trace_path=trace_path,
                reasoning_effort=reasoning_effort,
                event_callback=event_callback,
            )
            agent.run(prompt)
            update_conversation_metadata(username, conversation_id, prompt)

    def _stream_agent_run(
        self,
        username: str,
        conversation_id: str,
        prompt: str,
        reasoning_effort: str,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

        connected = True

        def send_event(event: dict[str, object]) -> None:
            nonlocal connected
            if not connected:
                return
            try:
                payload = json.dumps(event, ensure_ascii=False, default=str)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                connected = False

        try:
            send_event({"type": "stream_start"})
            self._run_agent(
                username,
                conversation_id,
                prompt,
                reasoning_effort,
                event_callback=send_event,
            )
            send_event(
                {
                    "type": "done",
                    "redirect": f"/chat/{conversation_id}?reasoning_effort={reasoning_effort}",
                }
            )
        except Exception as exc:
            traceback.print_exc()
            send_event({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    def _new_conversation(self, username: str) -> None:
        self._redirect_conversation(
            create_conversation(username),
            DEFAULT_REASONING_EFFORT,
        )

    def _delete_conversation(self, username: str, conversation_id: str) -> None:
        directory = conversation_paths(username, conversation_id)[0].parent
        with user_lock(username):
            with conversation_lock(username, conversation_id):
                if not directory.is_dir():
                    self.send_error(404)
                    return
                shutil.rmtree(directory)
        self._redirect_conversation(
            ensure_user_conversation(username),
            DEFAULT_REASONING_EFFORT,
        )

    def _login(self) -> None:
        try:
            form = self._read_form()
        except ValueError:
            self._send_html(400, render_login_page(error="Invalid request."))
            return

        username = normalize_username(form.get("username", [""])[0])
        password = form.get("password", [""])[0]
        if not USER_STORE.authenticate(username, password):
            self._send_html(
                401,
                render_login_page(username=username, error="Incorrect username or password."),
            )
            return
        self._start_session(username)

    def _register(self) -> None:
        try:
            form = self._read_form()
        except ValueError:
            self._send_html(400, render_register_page(error="Invalid request."))
            return

        username = normalize_username(form.get("username", [""])[0])
        password = form.get("password", [""])[0]
        confirm_password = form.get("confirm_password", [""])[0]
        try:
            username = validate_username(username)
        except ValueError as exc:
            self._send_html(400, render_register_page(username=username, error=str(exc)))
            return
        if not password:
            self._send_html(
                400,
                render_register_page(username=username, error="Password is required."),
            )
            return
        if password != confirm_password:
            self._send_html(
                400,
                render_register_page(username=username, error="Passwords do not match."),
            )
            return
        if not USER_STORE.create_user(username, password):
            self._send_html(
                409,
                render_register_page(username=username, error="Username is already registered."),
            )
            return
        self._start_session(username)

    def _start_session(self, username: str) -> None:
        session_token = secrets.token_urlsafe(32)
        with SESSIONS_LOCK:
            SESSIONS[session_token] = validate_username(username)
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = session_token
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
        session_token = self._session_token()
        if session_token is not None:
            with SESSIONS_LOCK:
                SESSIONS.pop(session_token, None)
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

    def _session_token(self) -> str | None:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        session = cookie.get(SESSION_COOKIE_NAME)
        return session.value if session is not None else None

    def _authenticated_user(self) -> str | None:
        session_token = self._session_token()
        if session_token is None:
            return None
        with SESSIONS_LOCK:
            return SESSIONS.get(session_token)

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
        expected_length = 3 if action else 2
        if len(parts) != expected_length or parts[0] != "chat":
            return None
        if action is not None and parts[2] != action:
            return None
        try:
            return validate_conversation_id(parts[1])
        except ValueError:
            return None

    def _redirect_home(self, reasoning_effort: str) -> None:
        self._redirect(f"/?reasoning_effort={reasoning_effort}")

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
    server = ThreadingHTTPServer((HOST, PORT), AgentRequestHandler)
    print(f"Agent web server: http://{HOST}:{PORT}")
    print("Registration: enabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
