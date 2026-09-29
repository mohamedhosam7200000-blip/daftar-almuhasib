"""Local web app: python -m khabeer.local.server

Serves the chat UI (web/dist-local) on http://127.0.0.1:8321 and runs each
message through LocalKhabeer. Listens on localhost only.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import MODEL, OUTPUT_DIR, LocalKhabeer, OllamaError

HOST = "127.0.0.1"
PORT = int(os.environ.get("KHABEER_PORT", "8321"))
UI_DIR = Path(__file__).resolve().parents[2] / "web" / "dist-local"
MAX_BODY = 1_000_000

_sessions: dict[str, LocalKhabeer] = {}
_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _session(sid: str) -> tuple[LocalKhabeer, threading.Lock]:
    with _registry_lock:
        if sid not in _sessions:
            _sessions[sid] = LocalKhabeer()
            _locks[sid] = threading.Lock()
        return _sessions[sid], _locks[sid]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Reject cross-site requests: only the page we serve may call the API.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden origin"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "الرسالة طويلة جداً"})
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad json"})
        sid = str(data.get("session") or "default")[:100]

        if self.path == "/api/reset":
            _session(sid)[0].reset()
            return self._json(HTTPStatus.OK, {"ok": True})
        if self.path != "/api/chat":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        text = str(data.get("text") or "").strip()
        if not text:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "empty message"})
        bot, lock = _session(sid)
        tools: list[dict] = []
        with lock:  # one message at a time per conversation
            try:
                result = bot.ask(text, on_tool=lambda n, a: tools.append({"name": n, "args": a}))
            except OllamaError as e:
                return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(e)})
        files = []
        for path in result["files"]:
            p = Path(path)
            files.append({"filename": str(p.relative_to(OUTPUT_DIR)),
                          "content": p.read_text(encoding="utf-8")})
        return self._json(HTTPStatus.OK, {"answer": result["answer"], "tools": tools, "files": files})


def main() -> int:
    if not (UI_DIR / "index.html").exists():
        print(f"الواجهة غير موجودة في {UI_DIR}. نفّذ داخل web/:  npm install && npm run build")
        return 1
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"خبير المحلي يعمل على {url}  (النموذج: {MODEL})")
    print(f"الملفّات تُحفظ في: {OUTPUT_DIR}")
    print("لإيقافه أغلق هذه النافذة أو اضغط Ctrl+C.")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
