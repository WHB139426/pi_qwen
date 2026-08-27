"""Minimal password-protected web entry point for the agent harness."""

from __future__ import annotations

import base64
import binascii
import hmac
import html
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs

from main import create_agent


HOST = "127.0.0.1"
PORT = 8765
USERNAME = "agent"
MAX_PROMPT_CHARS = 20_000
MAX_REQUEST_BYTES = 64 * 1024
CONVERSATION_PATH = Path("./tmp/web_conversation.json")
TRACE_PATH = Path("./tmp/web_trace.txt")
RUN_LOCK = Lock()


def render_page(*, prompt: str = "", output: str = "", error: str = "") -> bytes:
    prompt_html = html.escape(prompt)
    output_html = html.escape(output)
    error_html = html.escape(error)
    result = ""
    if output_html:
        result += f"<h2>Output</h2><pre>{output_html}</pre>"
    if error_html:
        result += f"<h2>Error</h2><pre>{error_html}</pre>"

    page = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Agent</title></head>
<body>
<h1>Agent</h1>
<form method="post" action="/run">
<textarea name="prompt" rows="12" cols="100" required>{prompt_html}</textarea><br>
<button type="submit">Run</button>
</form>
{result}
</body>
</html>
"""
    return page.encode("utf-8")


class AgentRequestHandler(BaseHTTPRequestHandler):
    access_token = ""

    def do_GET(self) -> None:
        if not self._authenticate():
            return
        if self.path != "/":
            self.send_error(404)
            return
        self._send_html(200, render_page())

    def do_POST(self) -> None:
        if not self._authenticate():
            return
        if self.path != "/run":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._send_html(400, render_page(error="Invalid request size."))
            return

        form = parse_qs(
            self.rfile.read(content_length).decode("utf-8"),
            keep_blank_values=True,
        )
        prompt = form.get("prompt", [""])[0].strip()
        if not prompt:
            self._send_html(400, render_page(error="Prompt is required."))
            return
        if len(prompt) > MAX_PROMPT_CHARS:
            self._send_html(
                400,
                render_page(prompt=prompt, error=f"Prompt exceeds {MAX_PROMPT_CHARS} characters."),
            )
            return
        if not RUN_LOCK.acquire(blocking=False):
            self._send_html(409, render_page(prompt=prompt, error="The agent is already running."))
            return

        try:
            agent = create_agent(
                conversation_path=CONVERSATION_PATH,
                trace_path=TRACE_PATH,
            )
            result = agent.run(prompt)
            self._send_html(200, render_page(prompt=prompt, output=result.answer))
        except Exception as exc:
            traceback.print_exc()
            self._send_html(
                500,
                render_page(prompt=prompt, error=f"{type(exc).__name__}: {exc}"),
            )
        finally:
            RUN_LOCK.release()

    def _authenticate(self) -> bool:
        authorization = self.headers.get("Authorization", "")
        try:
            scheme, encoded = authorization.split(" ", 1)
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            username, password, scheme = "", "", ""

        authorized = (
            scheme.lower() == "basic"
            and hmac.compare_digest(username, USERNAME)
            and hmac.compare_digest(password, self.access_token)
        )
        if authorized:
            return True

        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Agent"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def _send_html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    access_token = os.environ.get("AGENT_ACCESS_TOKEN", "")
    if not access_token:
        raise SystemExit("AGENT_ACCESS_TOKEN must be set")

    AgentRequestHandler.access_token = access_token
    server = ThreadingHTTPServer((HOST, PORT), AgentRequestHandler)
    print(f"Agent web server: http://{HOST}:{PORT}")
    print("Username: agent")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
